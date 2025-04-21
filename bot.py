
from game import *
from views import *
from usermanagement import *
from webconnector import *
from discord.ext import commands, tasks
from discord import app_commands
import requests
import copy
import os
import threading
import discord
import asyncio
import pickle


def get_random():
    randint = random.getrandbits(128)
    randstr = f"{randint:032x}"
    return randstr


class Beep(commands.Cog):
    CHANNEL_SETTINGS_TEXT = ["Quiz erlauben", "User Aktivierung erlauben", "Quiz modifizierbar", "Moderierte Quiz erlauben"]
    CHANNEL_SETTINGS_OPTION = ["quiz", "user_activated", "modifier", "moderated"]
    CHANNEL_SETTINGS_DEFAULT = [False, False, False, False]
    
    USER_SETTINGS_TEXT = ["Bei Review benachrichtigen"]
    USER_SETTINGS_OPTION = ["notify_review" ]
    USER_SETTINGS_DEFAULT = [False]
        
    def __init__(self, bot):
        self.bot = bot
        
        self.pools:dict = {}
        self.review=[]
        self.channel_settings:dict=dict()
        self.user_settings:dict=dict()
        self.userdb = {}
        self.request_codes = []
        self.request_codes_user = {}
        
        self.load_from_file()
        
        self.usr = UserManagement(self.userdb)
        self.current_quiz_sessions = dict()
        self.webconnector = WebConnector()
        self.answer_object = {}
    
    @tasks.loop(minutes=1)
    async def save_to_file(self, filename="data.pkl"):
        
        temp_filename = filename + '.tmp'
        data = {
            'pools': self.pools,
            'review': self.review,
            'channel_settings': self.channel_settings,
            'user_settings': self.user_settings,
            'userdb': self.usr.get_user_db(),
            'request_codes': self.request_codes,
            'request_codes_user': self.request_codes_user
        }
        with open(temp_filename, 'wb') as file:
            pickle.dump(data, file)
            file.flush()
            os.fsync(file.fileno()) 
        os.replace(temp_filename, filename)
    
    async def cog_load(self):
        self.save_to_file.start()

    def cog_unload(self):
        self.save_to_file.cancel()  
    
    @save_to_file.before_loop
    async def before_meine_task(self):
        await self.bot.wait_until_ready() 
        
        
    def load_from_file(self, filename="data.pkl"):
        try:
            with open(filename, 'rb') as file:
                data = pickle.load(file)

            self.pools = data.get('pools', {})
            self.review = data.get('review', [])
            self.channel_settings = data.get('channel_settings', {})
            self.user_settings = data.get('user_settings', {})
            self.userdb = data.get('userdb', {})
            self.request_codes = data.get('request_codes', [])
            self.request_codes_user = data.get('request_codes_user', {})

        except:
            print("No existing data file found. Starting fresh.")
            
    def get_pool(self, guild):
        if not guild: 
            return None
        
        guildid = guild
        if not isinstance(guild,str) and not isinstance(guild,int):
            guildid = guild.id
        
        if guildid not in self.pools:
            #p:Pool = Pool.parse_json(e)
            self.pools[guildid] = Pool()
            
        return self.pools[guildid]
    
    def add_to_review(self, q:Question, user_id, guild_id):
        for r in self.review:
            if r["question"].uuid == q.uuid:
                return False
            
        review_item = {"question": q, "user": user_id, "guild": guild_id, "time": time.time(), "reviewer":None, "status":None, "skip":[]}
        self.review.append(review_item)
        
        old = [e for e in self.review if (time.time() - int(e["time"])) >= 30 * 24 * 3600]
        for o in old:
            self.review.remove(o)
        return True
            
            
    @app_commands.command(name="review", description="Startet den Review-Prozess für neue Fragen")
    async def do_review(self, interaction:discord.Interaction):    
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        await self.review_now(interaction)
        
    async def review_now(self, interaction:discord.Interaction, iguild=None):
        if not iguild:
            iguild = interaction.guild
        
        guildid = iguild.id
            
        if not self.usr.check_if_mod(iguild, interaction.user):
            await interaction.response.send_message("Du besitzt leider keine Berechtigung um Fragen zu bearbeiten.", ephemeral=True)
            return
        
        if len(self.review)<=0:
            await interaction.response.send_message("Aktuell gibt es keine offenen Reviewaufträge.", ephemeral=True)
            return
        
        review_req = None
        for i in range(0, len(self.review)):
            req = self.review[i]
            if req["reviewer"] and req["reviewer"] != interaction.user.id:
                continue
            elif interaction.user.id in req["skip"]:
                continue
            elif guildid != req["guild"]:
                continue
            else:
                review_req=req
                break
        
        if not review_req:   
            await interaction.response.send_message("Aktuell gibt es keine offenen Reviewaufträge.", ephemeral=True)
            return
        else:
            if interaction.guild:
                await interaction.response.send_message("Starte Review.",ephemeral=True)
            else:
                await interaction.response.send_message("Nächste Frage.",ephemeral=True)
        
        
        if interaction.user.dm_channel is None:
            await interaction.user.create_dm()
        
        review_req["reviewer"] = interaction.user.id
        
        q: Question = review_req["question"]
        user_id = review_req["user"]
        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        guild_id = review_req["guild"]
        guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
        
        async def accept(interaction:discord.Interaction, q:Question):
            if review_req in self.review and review_req["reviewer"] == interaction.user.id:
                res = self.get_pool(guild_id).add_or_update(q)
                if res == "edit": 
                    await interaction.response.send_message("Frage erfolgreich aktualisiert.")
                if res == "add": 
                    await interaction.response.send_message("Frage erfolgreich hinzugefügt.")
                if review_req in self.review: self.review.remove(review_req)
        
        async def edit(interaction:discord.Interaction, q:Question):
            if review_req in self.review and review_req["reviewer"] == interaction.user.id:
                edit_req = {"question":q, "guild" : guild_id}
                await self.edit_now(interaction, q.uuid, edit_req=edit_req)
                if review_req in self.review: self.review.remove(review_req)
        
        async def skip(interaction:discord.Interaction, q:Question):
            if review_req in self.review:
                if review_req["reviewer"] == interaction.user.id:
                    review_req["reviewer"]=None
                review_req["skip"].append(interaction.user.id)
                await interaction.response.send_message("Frage wird übersprungen.")
            
        async def delete(interaction:discord.Interaction, q:Question):
            if review_req in self.review and review_req["reviewer"] == interaction.user.id:
                if review_req in self.review: self.review.remove(review_req)
                await interaction.response.send_message("Frage wurde verworfen.")
                
        view= QuizReview(q, accept, edit, skip, delete)
        
        await interaction.user.dm_channel.send(f"## Frage von {user.name} auf {guild.name}\n")
        
        
        if self.get_pool(guild_id).get_question_by_uuid(q.uuid):
            await interaction.user.dm_channel.send(f"**ACHTUNG**: Ersetzt bestehende Frage {q.uuid}")
        
        equals = self.get_pool(guild_id).check_equality(q)
        if len(equals)>0:
            qs = "[" + ", ".join([str(f.uuid) for f in equals]) + "]"
            qview = ShowQuestion(self, interaction.user, guild, [str(f.uuid) for f in equals])
            await interaction.user.dm_channel.send(f"**ACHTUNG**: Hohe Ähnlichkeit zu Frage(n) {qs} festgestellt!",view=qview)
        
        if q.has_image():
            image_file = discord.File(os.path.join("images", q.image), filename=q.image)
            await interaction.user.dm_channel.send(embed=QuizView.get_embed(q, image_file, show_answers=True), file=image_file)            
        else:
            await interaction.user.dm_channel.send(embed=QuizView.get_embed(q, show_answers=True))
        await interaction.user.dm_channel.send("Bitte wählen:", view=view)
        
        await interaction.user.dm_channel.send("Review fortsetzen", view=ContinueButton(self,interaction.user,iguild))
        
    @app_commands.command(name="show_question", description="Zeigt eine Frage an.")
    @app_commands.describe(uuid="UUID der Frage")
    async def show_question(self, interaction:discord.Interaction, uuid:str):       
        if not interaction.guild:
            await interaction.response.send_message(f"Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return 
        if not self.usr.check_if_mod(interaction.guild, interaction.user):
            await interaction.response.send_message("Du besitzt leider keine Berechtigung um Fragen anzusehen.", ephemeral=True)
            return
        
        guild = interaction.guild
        await self.show_question_now(interaction,uuid,guild)
        
    async def show_question_now(self, interaction:discord.Interaction, uuid:str, guild=None):  
        q:Question = self.get_pool(guild).get_question_by_uuid(uuid)
        if not q:
            await interaction.response.send_message(f"Frage {uuid} nicht gefunden.", ephemeral=True)
            return
            
        async def edit(interaction:discord.Interaction, q:Question):
            edit_req = {"question":q, "guild" : guild}
            await self.edit_now(interaction, q.uuid, edit_req=edit_req)

        async def delete(interaction:discord.Interaction, q:Question):
            await self.delete_now(interaction, q.uuid, guild)
            
            
        view = ShowQuestionOptions(q, on_edit=edit, on_delete=delete)
        
        if q.has_image():
            image_file = discord.File(os.path.join("images", q.image), filename=q.image)
            await interaction.response.send_message(embed=QuizView.get_embed(q, image_file, show_answers=True), file=image_file, view=view, ephemeral=True)            
        else:
            await interaction.response.send_message(embed=QuizView.get_embed(q, show_answers=True), view=view, ephemeral=True)
        
    
    @app_commands.command(name="members", description="Gibt einen Überblick zu den Berechtigungen.")
    async def members(self, interaction:discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(f"Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        l=""
        guild = interaction.guild
        all_users = self.usr.get_members_guild(guild)
 
        l+="### Für *"+str(interaction.guild.name)+"*\n"

        if all_users and len(all_users)>0:
            #{"owner": [], "admin": [], "mod":[]}
            for g in ["owner", "admin", "mod"]:
                l+= "> **"+ str(g).title() + "**: " 
                l+=", ".join(["<@"+str((await bot.fetch_user(u)).id)+">" for u in all_users[g]])
                if len(all_users[g])<=0:
                    l+=" *Keine*"
                l+="\n"
        else:
            l+= "*Keine*\n"    
        
        l+="\n\n"
        globals = self.usr.get_members_global()        
        if len(globals["owner"])>0:
            l+= "-# Bot Owner: " + ", ".join(["<@"+str((await bot.fetch_user(u)).id)+">" for u in globals["owner"]])+"\n"
        if len(globals["admin"])>0:
            l+= "-# Bot Admins: " + ", ".join(["<@"+str((await bot.fetch_user(u)).id)+">" for u in globals["admin"]])+"\n"
        
        await interaction.response.send_message(f"##  **Memberliste**  \n\n"+l+"", ephemeral=True)
                       
    
    @app_commands.command(name="whoami", description="Zeige die eigene Berechtigung an")
    @app_commands.describe(
        user="Den Status eines Nutzers abfragen (optional)"
    )
    async def whoami(self, interaction:discord.Interaction, user: discord.Member | None = None):
        if not user:
            user = interaction.user
            
        res = self.usr.check_privilege(interaction.guild,user)
        
        answ = UserManagement.lvl_to_string(res)
        if not interaction.guild:
            await interaction.response.send_message(f"Berechtigung für diesen Bot: {answ}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Berechtigung für diesen Server: {answ}", ephemeral=True)
              
              
    @app_commands.command(name="grant", description="Setzt Berechtigung für Benutzer")
    @app_commands.describe(user="Auswahl des Benutzers")
    @app_commands.describe(permission="Wähle: owner, admin, mod, user")
    async def grant(self, interaction:discord.Interaction, user: discord.Member, permission:str):
        if not user:
            return
        userid = user.id
        perm = None

        perm = UserManagement.string_to_lvl(permission)
            
        if not perm: 
            await interaction.response.send_message("Berechtigung unbekannt", ephemeral=True)
            return
        
        res = self.usr.grant(interaction.guild, interaction.user.id, userid, perm)
        await interaction.response.send_message(res["msg"], ephemeral=True)
        
    @app_commands.command(name="pause", description="Quizausführung anhalten/fortsetzen")
    async def pause_quiz(self, interaction:discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        if interaction.channel_id in self.current_quiz_sessions:
            curses:QuizSession = self.current_quiz_sessions[interaction.channel_id]
            
            if not self.usr.check_if_mod(interaction.guild, interaction.user) and not interaction.user==curses.user:
                await interaction.response.send_message("Du besitzt leider keine Berechtigung um ein Quiz zu beenden.", ephemeral=True)
                return
        
            async def on_next(channel_id,interaction:discord.Interaction):
                if channel_id in self.current_quiz_sessions:
                    self.current_quiz_sessions[channel_id].pause=False
                    
                if interaction:
                    await interaction.response.edit_message(content="Quiz wird fortgesetzt.", view=None)
                
            if not self.current_quiz_sessions[interaction.channel_id].pause:
                await interaction.response.send_message("Quiz wird pausiert.", view=QuizContinueButton(self,interaction.channel_id,on_next), ephemeral=True)
                self.current_quiz_sessions[interaction.channel_id].pause=True
            else:
                await on_next()
                
                
                  
    @app_commands.command(name="stop-quiz", description="Stopt ein Quiz")
    async def stop_quiz(self, interaction:discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        if interaction.channel_id in self.current_quiz_sessions:
            curses:QuizSession = self.current_quiz_sessions[interaction.channel_id]
            
            if not self.usr.check_if_mod(interaction.guild, interaction.user) and not interaction.user==curses.user:
                await interaction.response.send_message("Du besitzt leider keine Berechtigung um ein Quiz zu beenden.", ephemeral=True)
                return

            await interaction.response.send_message("Quiz beendet.")
            self.current_quiz_sessions[interaction.channel_id].stop()
            
            await asyncio.sleep(2)
            if interaction.channel_id in self.current_quiz_sessions:
                del self.current_quiz_sessions[interaction.channel_id] 
            return
        else:
            await interaction.response.send_message("Kein laufendes Quiz gefunden.", ephemeral=True)
               

    
    async def start_quiz_now(self, interaction: discord.Interaction, sesObj):
        
        if self.current_quiz_sessions.get(sesObj.channel_id, None):
            await interaction.response.edit_message(content="Quiz konnte nicht gestartet werden.")
            return
        
        self.prepare(interaction)
        
        if not sesObj.questions or len(sesObj.questions)<=0:
            await interaction.response.edit_message("Quiz konnte nicht gestartet werden: zu wenige Fragen.", ephemeral=True)
            return
        
        if not sesObj.channel_id:
            await interaction.response.edit_message("Dieser Kanal kann nicht genutzt werden.", ephemeral=True)
            return
        
        if self.current_quiz_sessions.get(interaction.channel_id, None):
            return
        
        channel_id = sesObj.channel_id
        self.channel_settings[channel_id]['quizsettings'] = sesObj.settings
        channel = self.bot.get_channel(channel_id)
        
        qs = QuizSession(sesObj.questions)
        sesObj.session=qs
        self.current_quiz_sessions[interaction.channel_id] = qs
        qs.user=interaction.user
        
        moderated = self.get_quiz_setting(channel_id)['moderated']
        
        session_point_list={}
        
        qs.start()
        
        mod_interaction = interaction
        
        
        await interaction.response.edit_message(content="Quiz wird gestartet")
                 
                  
        while qs.is_next_question():
            
            await self.check_pause(qs)
            if moderated:
                async def m_next(interaction:discord.Interaction):
                    
                    await interaction.response.edit_message(content="gestartet", view=None)
                    mod_interaction = interaction
                
                mod_view = NextRoundButton(self, m_next)
                await mod_interaction.followup.send(view=mod_view, ephemeral=True)
                
                timed_out = await mod_view.wait()  

            await self.check_pause(qs)
            qs.start_round()
            qsq: QuizSessionQuestion = qs.get_current_question()
            q: Question = qsq.question
            view = QuizView(qsq, sesObj)
            
            if q.has_image():
                image_file = discord.File(os.path.join("images", q.image), filename=q.image)
                embed = QuizView.get_embed(qsq, image_file)
                msg = await channel.send(embed=embed, view=view, file=image_file)
            else:
                embed = QuizView.get_embed(qsq)
                msg = await channel.send(embed=embed, view=view)
            
            await self.check_pause(qs)
            
            if moderated:
                inter = mod_interaction
                async def m_refresh(msg):
                        await msg.edit(content="Antworten: "+ str(qsq.anz_guesses()))
                async def m_close(interaction:discord.Interaction):
                    await interaction.response.edit_message(content="Runde geschlossen.", view=None)
                    mod_interaction = interaction
                
                mod_view = CloseRoundButton(self, m_close, m_refresh)
                msg = await mod_interaction.followup.send( view=mod_view, ephemeral=True, wait=True)

                mod_view.editmsg = msg
                
                timed_out = await mod_view.wait()  
            else:
                await asyncio.sleep(q.timeout)

            
            qsq.close()
            if not qs.is_running: break
            
            await self.check_pause(qs)
                  
            if self.get_quiz_setting(channel_id)['show_pub_answer']:
                answers=", ".join([str(a) for a in q.get_correct_list()])
                answers= answers + " "*max((100-len(answers)),0) 
                await channel.send(f"Richtige Antwort(en): || { answers } ||")
            
            rank = qs.prepare_rank()
            await view.update_all_answers()
            
            qs.end_round()
            
            await self.check_pause(qs)
            
            await asyncio.sleep(1)
            if not qs.is_running: break
            
            await self.check_pause(qs)
        
        if self.get_quiz_setting(channel_id)['points']:
            await channel.send(embed=create_award_embed(qs.get_final_rank_list()))
        else:
            await channel.send(f"Quiz beendet.")
            
        if interaction.channel_id in self.current_quiz_sessions:
            del self.current_quiz_sessions[interaction.channel_id] 


    async def check_pause(self, qs):
        while qs.pause: 
            await asyncio.sleep(1)
            
    #@app_commands.command(name="delete", description="Frage löschen")
    #@app_commands.describe(uuid="UUID der Frage")
    #Legacy
    async def delete(self, interaction: discord.Interaction, uuid:str):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return

        await self.delete_now(interaction, uuid)
        
    async def delete_now(self, interaction: discord.Interaction, uuid:str, guild=None):  
        if not guild:
            guild = interaction.guild
            
        if not self.usr.check_if_mod(guild, interaction.user):
            await interaction.response.send_message("Du besitzt leider keine Berechtigung um Fragen zu bearbeiten.", ephemeral=True)
            return
        
        q:Question = self.get_pool(guild).get_question_by_uuid(uuid)
        if not q: 
            await interaction.response.send_message(f"Frage {uuid} konnte nicht gefunden werden.", ephemeral=True)
            return
        
        self.get_pool(guild).remove_question(q)
        await interaction.response.send_message(f"Die Frage {q.uuid} wurde erfolgreich gelöscht.", ephemeral=True)
        
        
        
    
    #@app_commands.command(name="edit", description="Frage editieren")
    #@app_commands.describe(uuid="UUID der Frage")
    #Legacy
    async def edit(self, interaction: discord.Interaction, uuid:str): 
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        await self.edit_now(interaction, uuid)
        
        
    async def edit_now(self, interaction: discord.Interaction, uuid:str, edit_req=None):

        q:Question = None
        
        answer =None
        if edit_req:
            q=edit_req["question"]
            guild=edit_req["guild"]
        else:
            guild=interaction.guild
            q = self.get_pool(guild).get_question_by_uuid(uuid)
            
            
        if not q: 
            await interaction.response.send_message(f"Frage {uuid} konnte nicht gefunden werden.", ephemeral=True)
            return
            
        
        o = copy.deepcopy(q.get_json())
        if q.has_image():
            res = self.webconnector.image_to_json(q.image)
            o["image"] = res
        
        token = await self.webconnector.send_to_server([o])
        key = self.webconnector.generate_hourly_hash()
            
        newtoken = get_random()
        obj = {'token': newtoken, 'time': time.time(), 'userid': interaction.user.id, 'mod': self.usr.check_if_mod(guild, interaction.user), 'guild': guild.id}
        self.request_codes_user[newtoken]=obj
        self.request_codes.append(newtoken)
        
        url =BASE_URL + f"/index.html?update&key={key}&code={token}&newcode={newtoken}"
        
        lv = LinkView("Frage editieren", url)
        answer = await interaction.response.send_message("Die Frage kann nun auf der Webseite bearbeitet werden.", view=lv, ephemeral=True)
        self.answer_object[newtoken] = interaction
        self.answer_object[token] = interaction
        
 
    @app_commands.command(name="add_question", description="Eigene Fragen erzeugen")
    async def add_question(self, interaction: discord.Interaction):
        
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        guild = interaction.guild
        
        key = self.webconnector.generate_hourly_hash()
        token = get_random();
        url =BASE_URL + f"/index.html?create&key={key}&code={token}"
        lv = LinkView("Frage Erstellen", url)
        answer = await interaction.response.send_message("Fragen können auf der Webseite erzeugt werden. \n\nNach der Übermittlung erhältst du eine Benachrichtigung. Bitte berücksichtige, dass diese bis zu 5 Minuten dauern kann. Vielen Dank für deinen Beitrag!", view=lv, ephemeral=True)
        obj = {'token': token, 'time': time.time(), 'userid': interaction.user.id, 'mod': self.usr.check_if_mod(guild, interaction.user), 'guild': guild.id}
        self.request_codes_user[token]=obj
        self.request_codes.append(token)

        old = [e for e in self.request_codes_user.values() if (time.time() - int(e["time"])) >= 24 * 3600]
        for e in old:
            del self.request_codes_user[e["token"]]
            self.request_codes.remove(e["token"])
        
    @app_commands.command(name="load", description="Lade gesendete Fragen")
    @app_commands.describe(token="der Hex-Token von der Webseite")
    @app_commands.describe(review="Wahr setzen, falls die Fragen in ein Review sollen")
    async def load(self, interaction: discord.Interaction, token:str, review:bool | None = None ):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        if not self.usr.check_if_mod(interaction.guild, interaction.user):
            await interaction.response.send_message("Du besitzt leider keine Berechtigung um Fragen zu laden.", ephemeral=True)
            return
        
        if review is None:
            review = False
        
        
        await interaction.response.defer(ephemeral=True)
        erg = await self.webconnector.load_quiz(token)
        erg = json.dumps(erg)
        
        np:Pool = Pool.parse_json(erg)
        if not np:
            await interaction.followup.send( f"Leider konnte ich keine Daten unter diesem Token sammeln.",   ephemeral=True)
            return
        
        anz = len(np.get_questions())
        
        add = 0
        edit = 0
        prived = self.usr.check_if_mod(interaction.guild, interaction.user)
        curpool = self.get_pool(interaction.guild)
        
        for q in np.get_questions():
            if review:
                if self.add_to_review(q, user_id=interaction.user.id, guild_id=interaction.guild.id):
                    add+=1
            else:
                r = curpool.add_or_update(q)
                if r=="add": add+=1
                if r=="edit": edit+=1
                                                
        if review:
            await interaction.followup.send(f"Hallo, ich habe {add} neue Fragen/Aktualisierungen geladen und stehen nun für einen Review bereit.",   ephemeral=True)
            await self.notify_on_review(interaction.guild)    
        else:
            await interaction.followup.send(f"Hallo, ich habe {add} neue Fragen und {edit} Aktualisierungen geladen und stehen nun zur Verfügung.",   ephemeral=True)
                            
        return
    
    @app_commands.command(name="user_settings", description="Usereinstellungen bearbeiten.")
    async def user_settings(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        if not self.usr.check_if_mod(interaction.guild, interaction.user):
            await interaction.response.send_message("Du besitzt leider keine Berechtigung um die Kanaleinstellungen zu ändern.", ephemeral=True)
            return
        
        userid = interaction.user.id
        if userid not in self.user_settings:
            self.user_settings[userid] = dict()
            for opt,default in zip(Beep.USER_SETTINGS_OPTION, Beep.USER_SETTINGS_DEFAULT):
                self.user_settings[userid][opt] = default
        
        await interaction.response.send_message(
            "Aktiviere oder deaktiviere die Einstellungen durch Betätigung der Buttons.",
            view=UserSettingsView(userid,self.user_settings[userid]),
            ephemeral=True
        )    
        
    @app_commands.command(name="channel_settings", description="Kanaleinstellungen bearbeiten.")
    async def channel_settings(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        self.prepare(interaction)
        
        if not self.usr.check_if_admin(interaction.guild, interaction.user):
            await interaction.response.send_message("Du besitzt leider keine Berechtigung um die Kanaleinstellungen zu ändern.", ephemeral=True)
            return
        
        channel_id = interaction.channel_id
        chansettings = self.channel_settings[channel_id]['channelsettings'] 
        
        await interaction.response.send_message(
            "Aktiviere oder deaktiviere die Einstellungen durch Betätigung der Buttons.",
            view=ChannelSettingsView(channel_id,chansettings),
            ephemeral=True
        )
    
    @app_commands.command(name="start_quiz", description="Ein neues Quiz starten.")
    async def start_quiz(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Dieser Befehl kann nur auf einem Server ausgeführt werden.", ephemeral=True)
            return
        
        self.prepare(interaction)
        channel = interaction.channel
        channel_id=interaction.channel_id
        
        if not channel_id:
            return
    
        if not self.get_chan_setting(channel_id)['quiz'] and not self.usr.check_if_owner(interaction.guild, interaction.user):
            await interaction.response.send_message("In diesem Kanal ist die Aktivierung nicht erlaubt.", ephemeral=True)
            return
            
        if not self.get_chan_setting(channel_id)['user_activated']:
            if not self.usr.check_if_mod(interaction.guild, interaction.user):
                await interaction.response.send_message("Du besitzt leider keine Berechtigung um ein Quiz zu starten.", ephemeral=True)
                return
        
        if interaction.channel_id in self.current_quiz_sessions and self.current_quiz_sessions[interaction.channel_id]:
            await interaction.response.send_message("Es läuft bereits eine Quiz-Session in diesem Kanal.", ephemeral=True)
            return
        
        sesObj:QuizSessionOption = QuizSessionOption(self) 
        sesObj.user=interaction.user
        sesObj.guild=interaction.guild
        sesObj.pool=copy.deepcopy(self.get_pool(interaction.guild))
        sesObj.channel_id=channel_id
        sesObj.settings = self.channel_settings[channel_id]['quizsettings'].copy()
        
        if sesObj.pool.count == 0:
            await interaction.response.send_message("Aktuell sind keine Fragen verfügbar.", ephemeral=True)
            return
        
        view = KategorieView(sesObj, interaction)

        await interaction.response.send_message(
            "Wähle eine Kategorie aus dem Dropdown. Klicke **Fertig**, wenn du fertig bist.",
            view=view,
            ephemeral=True
        )
    
    def get_chan_setting(self, channel_id):
        return self.channel_settings[channel_id]['channelsettings']
    
    def get_quiz_setting(self, channel_id):
        return self.channel_settings[channel_id]['quizsettings']
    
    def prepare(self, interaction: discord.Interaction):
        channel_id=interaction.channel_id
        self.channel_settings[channel_id]=self.channel_settings.get(channel_id, dict())
        
        chanset = self.channel_settings[channel_id]
        chanset['quizsettings']=chanset.get('quizsettings', dict())
        chanset['channelsettings']=chanset.get('channelsettings', dict())
        
        for o,d in zip(QuizSessionOption.FEATURES_OPTION,QuizSessionOption.FEATURES_DEFAULT):
            if o not in chanset['quizsettings']:
                chanset['quizsettings'][o] = d

        for o,d in zip(Beep.CHANNEL_SETTINGS_OPTION,Beep.CHANNEL_SETTINGS_DEFAULT):
            if o not in chanset['channelsettings']:
                chanset['channelsettings'][o] = d
                       
    async def on_file_found(self, token):
        self.request_codes.remove(token)
        await asyncio.sleep(1)
        
        erg = await self.webconnector.load_quiz(token)
        erg = json.dumps(erg)
        
        np:Pool = Pool.parse_json(erg)
        
        user_id = self.request_codes_user[token]['userid']
        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        
        anz = len(np.get_questions())
        add = 0
        edit = 0
        prived = self.request_codes_user[token]['mod']
        curpool = self.get_pool(self.request_codes_user[token]["guild"])
        
        answer:discord.Interaction = self.answer_object.get(token, None)

        for q in np.get_questions():
            if prived:
                r = curpool.add_or_update(q)
                if r=="add": add+=1
                if r=="edit": edit+=1
            else:
                self.add_to_review(q, user_id=user_id, guild_id=self.request_codes_user[token]["guild"])
                pass
        
        if answer:
            await answer.edit_original_response(content="Ich habe die Frage erfolgreich bearbeitet und hinzugefügt.", view=None)
        else:                 
            if self.request_codes_user[token]['mod']:
                await user.send(f"Hallo, ich habe {add} neue Fragen und {edit} Aktualisierungen geladen und verarbeitet. Als Moderator wurden deine Fragen sofort hinzugefügt und sind jetzt verfügbar.")
                  
            else:
                await user.send(f"Hallo, ich habe {anz} neue Fragen/Aktualisierungen geladen und werden nach einem Review verfügbar sein. Vielen Dank!")
                await self.notify_on_review(self.request_codes_user[token]["guild"])  
        
        if token in self.request_codes_user:
            del self.request_codes_user[token]
        if token in self.answer_object:
            del self.answer_object[token]

    
    async def notify_on_review(self, guild):
        if isinstance(guild,str) or isinstance(guild,int):
            guild = self.bot.get_guild(guild) or await self.bot.fetch_guild(guild)
        
        all_members = self.usr.get_all_members_userid(guild)
        
        for user_id in all_members:
            if user_id in self.user_settings and self.user_settings[user_id]["notify_review"]:
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    await user.send(f"Auf {guild.name} stehen neue Fragen für den Review bereit.", view=ReviewNowButton(self,user,guild))

                except Exception as e:             
                    pass
        

class QuizSessionOption:
    FEATURES_TEXT = ["Antworten öffentlich anzeigen", "Antwort privat anzeigen", "Eigene Moderation", "Punkte zählen"]
    FEATURES_OPTION = ["show_pub_answer", "show_priv_answer", "moderated", "points"]
    FEATURES_DEFAULT = [False, False, False, False]
    
    def __init__(self, bot:Beep):
        self.bot:Beep =bot
        self.session:QuizSession=None
        self.questions:list[Question]=None
        self.settings:dict=dict()
        self.pool:Pool=None
        self.channel_id=None
        self.user = None
        self.guild = None

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.beep:Beep=Beep(self)
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.add_cog(self.beep)
        await self.tree.sync(guild=discord.Object(id=1340683105056460951))  
        await create_polling_thread(self.beep)
        await self.tree.sync()


def poll_web_interface(loop, bot):
    max_timeout = 60  
    while True:
        try:
            if len(bot.request_codes)==0:
                time.sleep(5)
                continue
                
            time.sleep(0.5) 
            files = ",".join(bot.request_codes)
            url = f'http://{BASE_DOMAIN}/checker.php?files={files}'
            response = requests.get(url, timeout=max_timeout)
            
            if response.text.startswith("ready"):
                loop.call_soon_threadsafe(asyncio.create_task, bot.on_file_found(response.text.split(":")[1]))
                time.sleep(2)
        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.RequestException as e:
            time.sleep(5)

async def create_polling_thread(bot):
    loop = asyncio.get_running_loop()
    polling_thread = threading.Thread(target=poll_web_interface, args=(loop, bot), daemon=True)
    polling_thread.start()
    await asyncio.sleep(3)
        
if __name__ == "__main__":
    bot = Bot()

    bot.run("")
    


