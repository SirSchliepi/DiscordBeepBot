import discord
from discord.ui import View, Select
from bot import Beep,QuizSessionOption
from game import *
from discord.ext import tasks



class QuizReview(discord.ui.View):
    def __init__(self, q:Question, on_accept, on_edit, on_skip, on_delete):
        super().__init__(timeout=600)
        self.q=q
        self._on_accept = on_accept
        self._on_skip = on_skip
        self._on_delete = on_delete
        self._on_edit = on_edit
        pass

    @discord.ui.button(label="⏭️ Überspringen", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._on_skip(interaction, self.q)
    
    @discord.ui.button(label="❌ Löschen", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._on_delete(interaction, self.q)

    @discord.ui.button(label="✅ Akzeptieren", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._on_accept(interaction, self.q)

    @discord.ui.button(label="✏️ Editieren & Akzeptieren", style=discord.ButtonStyle.primary)
    async def edit_and_accept(self, interaction: discord.Interaction, _: discord.ui.Button):  
        await self._on_edit(interaction, self.q)


class ShowQuestion(discord.ui.View):
    def __init__(self, beep, user, guild, uuid_list, *, timeout: float = 600.0):
        super().__init__(timeout=timeout)
        self.beep:Beep=beep
        self.guild=guild
        self.user=user
        self.uuid_list=uuid_list

    @discord.ui.button(label="Anzeigen", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, _: discord.ui.Button):
        
        for uuid in self.uuid_list:
            await self.beep.show_question_now(interaction,uuid=uuid,guild=self.guild)
            break

class ShowQuestionOptions(discord.ui.View):
    def __init__(self, q:Question, on_edit, on_delete):
        super().__init__(timeout=600)
        self.q=q
        self._on_delete = on_delete
        self._on_edit = on_edit
        pass

    @discord.ui.button(label="❌ Löschen", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._on_delete(interaction, self.q)

    @discord.ui.button(label="✏️ Editieren", style=discord.ButtonStyle.primary)
    async def edit_and_accept(self, interaction: discord.Interaction, _: discord.ui.Button):  
        await self._on_edit(interaction, self.q)



class ReviewNowButton(discord.ui.View):
    def __init__(self, beep, user, guild, *, timeout: float = 600.0):
        super().__init__(timeout=timeout)
        self.beep:Beep=beep
        self.guild=guild
        self.user=user

    @discord.ui.button(label="Starte Review", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.beep.review_now(interaction, self.guild)
                   
class ContinueButton(discord.ui.View):

    def __init__(self, beep, user, guild, *, timeout: float = 600.0):
        super().__init__(timeout=timeout)
        self.beep:Beep=beep
        self.guild=guild
        self.user=user

    @discord.ui.button(label="Fortsetzen", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.beep.review_now(interaction, self.guild)

class QuizContinueButton(discord.ui.View):
    def __init__(self, beep, channel_id, on_next,*, timeout: float = 6000.0):
        super().__init__(timeout=timeout)
        self.beep:Beep=beep
        self._on_next = on_next
        self.channel_id=channel_id
        self.confirmed: bool | None = None 

    @discord.ui.button(label="Fortsetzen", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, _: discord.ui.Button):
        for item in self.children:
            item.disabled = True
                        
        self.confirmed = True
        await self._on_next(self.channel_id, interaction)
        self.stop()  
        
    async def on_timeout(self) -> None:
        await self._on_next(self.channel_id, None)
        
    
    
          
class NextRoundButton(discord.ui.View):
    def __init__(self, beep, on_next,*, timeout: float = 1500.0):
        super().__init__(timeout=timeout)
        self.beep:Beep=beep
        self._on_next = on_next
        self.confirmed: bool | None = None 

    @discord.ui.button(label="Runde starten", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        await self._on_next(interaction)
        self.stop()  
        

class CloseRoundButton(discord.ui.View):
    def __init__(self, beep, on_next, refresher,*, timeout: float = 1500.0):        
        super().__init__(timeout=timeout)
        self.beep:Beep=beep
        self._on_next = on_next
        self._refresher = refresher
        self.updater.start()  
        self.confirmed: bool | None = None 
        self.editmsg=None
        
    @discord.ui.button(label="Runde schließen", style=discord.ButtonStyle.success)
    async def cont(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.confirmed = True
        await self._on_next(interaction)    
        self.updater.cancel()
        self.stop()    
 
    @tasks.loop(seconds=3)
    async def updater(self):
        if self.editmsg:
            await self._refresher(self.editmsg)
         
    async def on_timeout(self):
        self.updater.cancel()
                 
        
class QuizView(discord.ui.View):
    def __init__(self, qsq: QuizSessionQuestion, sesObj:QuizSessionOption):
        
        tout = qsq.get_timeout()
        if sesObj.settings['moderated']: 
            tout=1500
            
        super().__init__(timeout=tout)
        self.qsq: QuizSessionQuestion = qsq
        self.sesObj = sesObj
        self.question = qsq.question
        self.correct_list = self.question.get_correct_list()
        self.reactions = dict()
        self.over=False
        
        
        for a in qsq.get_answers():
            self.add_item(
                QuizView.QuizButton(self, qsq, answer=a, correct=a.is_correct())
            )

    @classmethod
    def get_embed(cls, qsq, image_file=None, show_answers=False):
        
        t = ""
        if isinstance(qsq, QuizSessionQuestion):
            q: Question = qsq.question
            t += "Quizfrage " + str(qsq.number) + "/" + str(qsq.total)
        else:
            q: Question = qsq
            t += "Quizfrage"
        
        if q.is_multiple():
            t += "   (Mehrfachauswahl)"
        embed = discord.Embed(title=t, description=q.question+"\n\n")

        if q.has_sourcecode():
            embed.add_field(name="Quelltext", value="```" + q.sourcecode + "```")
            
        if image_file:
            embed.set_image(url="attachment://"+ image_file.filename)
        
        if show_answers:
            i=1
            for ans in q.answers:
                a:Answer = ans
                embed.add_field(name=f"Antwort {i}  "+ ("[Korrekt]" if a.correct else ""), value=a.answer + " " , inline=False)
                i+=1
                

        katstring = ", ".join(q.get_categories())
        embed.set_footer(text="Zeit: " + str(q.timeout) + "s | Kategorie: " + katstring + " | " + q.uuid)
        return embed

    async def update_all_answers(self):
        self.over=True
        answers = {}
        for user,original in self.reactions.items():
            e = self.get_response_text(user)
            answers[original] = e
        
        for original,emb in answers.items():
            await original.edit(embed=emb)
            
        
    def get_response_text(self,user):
        cur_answers = self.qsq.get_guesses_by_user(user)

        embed = discord.Embed(
            title="Auswahl",
            description=""
        )
        
        
        n = str(", ".join([str(a) for a in cur_answers]))
        if len(cur_answers)>1:
            embed.add_field(name="Deine Antworten", value=n, inline=False)
        else:
            embed.add_field(name="Deine Antwort", value=n, inline=False)

        if self.over and self.sesObj.settings['show_priv_answer']:
     
            corr_list=", ".join([str(a) for a in self.correct_list]) 
            if cur_answers == self.correct_list:
                embed.add_field(name="Richtige Antwort!", value="", inline=False)
                embed.color=discord.Color.green()
            else:
                r = "||" + corr_list+ "_"*max((100-len(corr_list)),0)  + "||"
                embed.color=discord.Color.red()
                embed.add_field(name="## Leider falsch!", value="", inline=False)
                embed.add_field(name="Richtige Antworten", value=r, inline=False) 
            
        if self.over and self.sesObj.settings['points']:
            punkte = str(self.sesObj.session.get_current_point(user))
            embed.add_field(name="Aktuelle Punktzahl", value=f"⭐ **{str(punkte)} Punkte**", inline=False)
            
        #embed.set_footer(text="Quiz-Bot | Viel Erfolg weiterhin!")
               
        return embed
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
            
    class QuizButton(discord.ui.Button):
        def __init__(self, qv, qsq: QuizSessionQuestion, answer: Answer, correct: bool):
            super().__init__(label=str(answer), style=discord.ButtonStyle.primary)
            self.answer: Answer = answer
            self.correct = correct
            self.qsq: QuizSessionQuestion = qsq
            self.qv = qv

        async def callback(self, interaction: discord.Interaction):
            if not self.qsq.is_open():
                return
            
            self.qsq.add_answer(SessionGuess(interaction.user, self.answer))
            n = self.qv.get_response_text(interaction.user)

            if interaction.user in self.qv.reactions:
                original = self.qv.reactions[interaction.user]
                await original.edit(embed=n)
                await interaction.response.defer()
            else:
                await interaction.response.send_message(embed=n, ephemeral=True)
                original = await interaction.original_response()
                self.qv.reactions[interaction.user] = original
            
            
class KategorieView(discord.ui.View):
    def __init__(self, sesObj: QuizSessionOption, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.ausgewaehlt = []
        self.max_fragen = 25
        self.sesObj = sesObj
        self.interaction = interaction
        self.add_item(self.KategorieSelect(self.sesObj.pool.get_categories(), self))

    async def update_message(self, interaction: discord.Interaction, feedback: str = None):
        anz = len(self.sesObj.pool.get_questions(self.ausgewaehlt))
        ausgewaehlt_text = ", ".join(self.ausgewaehlt) if self.ausgewaehlt else "Keine"
        content = (
            f"🗃️ **Ausgewählte Kategorien:** {ausgewaehlt_text}\n"
            f"📌 **Fragen verfügbar:** {anz}\n"
            f"🎯 **Maximale Anzahl Fragen:** {self.max_fragen}\n"
            f"\nWähle weitere Kategorien oder ändere die maximale Anzahl."
        )

        if feedback:
            content = f"{feedback}\n\n{content}"

        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Fertig", style=discord.ButtonStyle.success)
    async def fertig_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        questions = self.sesObj.pool.get_questions(self.ausgewaehlt)
        if len(questions) > self.max_fragen:
            questions = questions[:self.max_fragen]

        self.sesObj.questions = questions
        ausgewaehlt_text = ", ".join(self.ausgewaehlt) if self.ausgewaehlt else "Keine Kategorie ausgewählt."

        await interaction.response.edit_message(
            content=(
                f"✅ **Auswahl abgeschlossen!**\n\n"
                f"🗃️ **Kategorien:** {ausgewaehlt_text}\n"
                f"🎯 **Fragen:** {len(questions)}"
            ),
            view=QuizSettingsView(self.sesObj)
        )

    @discord.ui.button(label="Fragenanzahl festlegen", style=discord.ButtonStyle.primary)
    async def set_max_questions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.MaxFragenModal(self))

    class KategorieSelect(discord.ui.Select):
        def __init__(self, kategorien: list[str], parent):
            self.parent: KategorieView = parent
            options = [discord.SelectOption(label=kategorie) for kategorie in kategorien]

            super().__init__(
                placeholder="Wähle Kategorien",
                min_values=1,
                max_values=len(kategorien),
                options=options
            )

        async def callback(self, interaction: discord.Interaction):
            self.parent.ausgewaehlt = self.values
            await self.parent.update_message(interaction, feedback="✅ **Kategorien aktualisiert!**")

    class MaxFragenModal(discord.ui.Modal, title="Maximale Fragen festlegen"):
        anzahl = discord.ui.TextInput(
            label="Maximale Anzahl Fragen",
            placeholder="z.B. 25",
            required=True,
            default="25",
            max_length=3
        )

        def __init__(self, parent_view):
            super().__init__()
            self.parent_view: KategorieView = parent_view

        async def on_submit(self, interaction: discord.Interaction):
            try:
                wert = int(self.anzahl.value)
                if wert <= 0:
                    raise ValueError
                self.parent_view.max_fragen = wert
                feedback = f"✅ **Maximale Fragen auf {wert} gesetzt!**"
            except ValueError:
                feedback = "❌ **Bitte gib eine gültige positive Zahl ein.**"

            await self.parent_view.update_message(interaction, feedback=feedback)



class QuizSettingsView(discord.ui.View):
    
    def __init__(self, sesObj:QuizSessionOption):
        super().__init__(timeout=300)
        self.sesObj:QuizSessionOption=sesObj
        self.channel_id = sesObj.channel_id
        self.beepbot:Beep = sesObj.bot
        self.quiz_settings:dict = sesObj.settings
        
        if self.beepbot.get_chan_setting(self.channel_id)['modifier'] or self.beepbot.usr.check_if_mod(sesObj.guild, sesObj.user):
            for text,feature in zip(QuizSessionOption.FEATURES_TEXT,QuizSessionOption.FEATURES_OPTION):
                button = self.FeatureButton(text, feature, self)
                if feature=="moderated" and not self.beepbot.get_chan_setting(self.channel_id)['moderated']:
                    self.quiz_settings[feature] = False
                    continue
                
                self.add_item(button)
              
        self.add_item(self.StartButton(sesObj,self)) #Quiz starten!

    class FeatureButton(discord.ui.Button):
        def __init__(self, text:str, feature: str, parent):
            self.feature = feature
            self.text = text
            self.parent:QuizSettingsView = parent
            current_state = self.parent.quiz_settings[feature]
            label = f"{text}: {'✅' if current_state else '❌'}"
            super().__init__(label=label, style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            self.parent.quiz_settings[self.feature] = not self.parent.quiz_settings[self.feature]
            self.parent.sesObj.settings=self.parent.quiz_settings
            await interaction.response.edit_message(view=QuizSettingsView(self.parent.sesObj))

        
    class StartButton(discord.ui.Button):
        def __init__(self, sesObj:QuizSessionOption, parent):
            super().__init__(label="✅ Quiz starten", style=discord.ButtonStyle.success)
            self.parent:QuizSettingsView=parent
            self.sesObj = sesObj

        async def callback(self, interaction: discord.Interaction):
            self.sesObj.settings=self.parent.quiz_settings
            view = self.view
            for child in view.children:
                child.disabled = True

            await self.sesObj.bot.start_quiz_now(interaction,self.sesObj)
            


class UserSettingsView(discord.ui.View):
    
    def __init__(self, userid, settings:dict):
        super().__init__(timeout=300)

        self.settings=settings
        self.userid=userid
        
        # Dynamisch Buttons hinzufügen
        for text,feature in zip(Beep.USER_SETTINGS_TEXT,Beep.USER_SETTINGS_OPTION):
            self.add_item(self.FeatureButton(text, feature, self))
              
    class FeatureButton(discord.ui.Button):
        def __init__(self, text:str, feature: str, parent):
            self.feature = feature
            self.text = text
            self.parent:UserSettingsView = parent
            current_state = self.parent.settings[feature]
            label = f"{text}: {'✅' if current_state else '❌'}"
            if current_state:
                super().__init__(label=label, style=discord.ButtonStyle.green)
            else:
                super().__init__(label=label, style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            self.parent.settings[self.feature] = not self.parent.settings[self.feature]
            await interaction.response.edit_message(view=UserSettingsView(self.parent.userid,self.parent.settings))



class ChannelSettingsView(discord.ui.View):
    
    def __init__(self, channel_id, settings:dict):
        super().__init__(timeout=300)

        self.channel_id = channel_id
        self.channel_settings:dict = settings
        
        # Dynamisch Buttons hinzufügen
        for text,feature in zip(Beep.CHANNEL_SETTINGS_TEXT,Beep.CHANNEL_SETTINGS_OPTION):
            self.add_item(self.FeatureButton(text, feature, self))
              
    class FeatureButton(discord.ui.Button):
        def __init__(self, text:str, feature: str, parent):
            self.feature = feature
            self.text = text
            self.parent:ChannelSettingsView = parent
            current_state = self.parent.channel_settings[feature]
            label = f"{text}: {'✅' if current_state else '❌'}"
            if current_state:
                super().__init__(label=label, style=discord.ButtonStyle.green)
            else:
                super().__init__(label=label, style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            # Toggle Setting
            self.parent.channel_settings[self.feature] = not self.parent.channel_settings[self.feature]
            await interaction.response.edit_message(view=ChannelSettingsView(self.parent.channel_id,self.parent.channel_settings))

class LinkView(discord.ui.View):
    def __init__(self, link_text:str, link_url:str):
        super().__init__(timeout=600)
        button = discord.ui.Button(label=link_text, url=link_url)
        self.add_item(button)
        


class GuildSelectView(discord.ui.View):
    def __init__(self, user, guilds, *, timeout: float = 60):
        super().__init__(timeout=timeout)        # eigener Timeout (Sek.)
        self.user = user
        self.guilds = guilds
        self.selected_guild: discord.Guild | None = None

        self.select = discord.ui.Select(
            placeholder="Wähle die Guild aus",
            options=[discord.SelectOption(label=g.name, value=str(g.id))
                     for g in guilds]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message(
                "Das ist nicht dein Befehl!", ephemeral=True
            )
            return

        gid = int(self.select.values[0])
        self.selected_guild = discord.utils.get(self.guilds, id=gid)

        await interaction.response.send_message(
            f"Du hast **{self.selected_guild.name}** gewählt.", ephemeral=True
        )

        self.stop()


def create_award_embed(score_dict: dict[str, int]) -> discord.Embed:
    sorted_scores = sorted(score_dict.items(), key=lambda x: x[1], reverse=True)[:3]

    medal = {1: "🥇", 2: "🥈", 3: "🥉"}
    embed = discord.Embed(
        title="🏆  Siegerehrung",
        description="Hier sind die drei Besten – Glückwunsch!",
        color=discord.Color.gold(),
    )

    lines = []
    for place, (name, points) in enumerate(sorted_scores, start=1):
        lines.append(f"{medal[place]} **{name}** — **{points} Punkte**")

    embed.add_field(name="Podium", value="\n".join(lines) if len(lines)>0 else " :desert:", inline=False)
    if len(lines)>0:
        embed.set_footer(text="Weiter so! ✨")
    return embed