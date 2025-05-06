import discord
from discord.ui import View, Select, Button
from bot import Beep,QuizSessionOption
from game import *
from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont
import platform





class QuizImageGenerator:
    def __init__(self, width=800, height=600, font_size=32, tracking=1.3, line_spacing=15):
        self.width = width
        self.height = height
        self.font_size = font_size
        self.tracking = tracking
        self.line_spacing = line_spacing
        self.background_color = (7, 44, 66)
        self.text_color = (255, 255, 255)
        self.shadow_color = (0, 0, 100)
        self.border_width = 4
        self.corner_radius = 40
        self.start_color = (110, 170, 225, 150)
        self.end_color = (0, 110, 150, 150)
        self.font_path = self._get_font_path()
        self.font = ImageFont.truetype(self.font_path, self.font_size)

    def _get_font_path(self):
        if platform.system() == "Windows":
            return "C:/Windows/Fonts/Carlito-Bold.ttf"
        elif platform.system() == "Darwin":
            return "/Library/Fonts/Arial Bold.ttf"
        else:
            return "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf"

    def _get_text_width_with_tracking(self, text):
        total_width = 0
        for i, char in enumerate(text):
            char_width = self.font.getbbox(char)[2] - self.font.getbbox(char)[0]
            total_width += char_width
            if i < len(text) - 1:
                total_width += self.tracking
        return total_width

    def _draw_text_with_tracking(self, draw, position, text):
        x, y = position
        for char in text:
            draw.text((x + 2, y + 2), char, font=self.font, fill=self.shadow_color)
            draw.text((x, y), char, font=self.font, fill=self.text_color)
            char_width = self.font.getbbox(char)[2] - self.font.getbbox(char)[0]
            x += char_width + self.tracking

    def _wrap_text(self, text, max_width):
        draw = ImageDraw.Draw(Image.new('RGBA', (self.width, 1)))
        paragraphs = text.split('\n')
        lines = []
        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current_line = words[0]
            for word in words[1:]:
                test_line = current_line + " " + word
                if self._get_text_width_with_tracking(test_line) <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
        return lines

    def _draw_linear_gradient_border(self, img, rect):
        gradient = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw_gradient = ImageDraw.Draw(gradient)
        steps = max(rect[2] - rect[0], rect[3] - rect[1]) * 2
        for i in range(steps):
            ratio = i / steps
            r = int(self.start_color[0] * (1 - ratio) + self.end_color[0] * ratio)
            g = int(self.start_color[1] * (1 - ratio) + self.end_color[1] * ratio)
            b = int(self.start_color[2] * (1 - ratio) + self.end_color[2] * ratio)
            a = int(self.start_color[3] * (1 - ratio) + self.end_color[3] * ratio)
            x = rect[0] + i
            y = rect[1] + i
            draw_gradient.line([(x, rect[1]), (rect[0], y)], fill=(r, g, b, a))
        mask = Image.new('L', img.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(rect, radius=self.corner_radius, outline=255, width=self.border_width)
        gradient.putalpha(mask)
        return Image.alpha_composite(img, gradient)

    def generate_image(self, text, uuid, additional_image_path=None):
        final_border_size = 10
        wrapped_lines = self._wrap_text(text, self.width - 40)
        font_height = self.font.getbbox('Hg')[3] - self.font.getbbox('Hg')[1]
        line_height = font_height + self.line_spacing
        total_text_height = len(wrapped_lines) * line_height
        inner_content_height = total_text_height + 80

        additional_image = None
        additional_image_height = 0
        side_margin = 40

        if additional_image_path:
            # Öffne das Bild
            additional_image = Image.open(additional_image_path).convert("RGBA")
            original_width, original_height = additional_image.size

            target_min_width = 350
            target_max_width = 750
            target_max_height = 400

            scale_factors = []
            if original_width < target_min_width:
                scale_factors.append(target_min_width / original_width)
            if original_width > target_max_width:
                scale_factors.append(target_max_width / original_width)
            if original_height > target_max_height:
                scale_factors.append(target_max_height / original_height)

            scale_factor = min(scale_factors) if scale_factors else 1.0

            if scale_factor != 1.0:
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                additional_image = additional_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            additional_image_height = additional_image.height
            inner_content_height += additional_image_height + 20
            
        self.height = max(inner_content_height, 150)
        inner_width = self.width
        if additional_image:
            inner_width = max(self.width, additional_image.width + side_margin * 2)

        inner_image = Image.new('RGBA', (inner_width, self.height), (0, 0, 0, 0))

        background_rect = Image.new('RGBA', (inner_width, self.height), (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(background_rect)
        bg_draw.rounded_rectangle(
            [self.border_width, self.border_width, inner_width - self.border_width - 1, self.height - self.border_width - 1],
            radius=self.corner_radius,
            fill=self.background_color
        )

        inner_image = Image.alpha_composite(inner_image, background_rect)
        inner_image = self._draw_linear_gradient_border(inner_image, [0, 0, inner_width - 1, self.height - 1])

        draw = ImageDraw.Draw(inner_image)
        start_y = (self.height - total_text_height - additional_image_height) / 2

        for i, line in enumerate(wrapped_lines):
            line_width = self._get_text_width_with_tracking(line)
            x = (inner_width - line_width) / 2
            y = start_y + i * line_height
            self._draw_text_with_tracking(draw, (x, y), line)

        if additional_image:
            image_x = max((inner_width - additional_image.width) // 2, side_margin)
            image_y = start_y + len(wrapped_lines) * line_height + 20
            inner_image.paste(additional_image, (image_x, int(image_y)), additional_image)

        border_size = 10
        total_width = max(inner_width + 2 * border_size,800)
        total_height = self.height + 2 * final_border_size

        final_image = Image.new('RGBA', (total_width, total_height), (0, 0, 0, 0))
        final_image.paste(inner_image, (border_size, border_size), inner_image)

        filename = f"quizfrage_{uuid}.png"
        filepath = os.path.join("images", filename)
        final_image.save(filepath, format="PNG")
        return filepath




class QuizReview(discord.ui.View):
    def __init__(self, q:Question, on_accept, on_edit, on_skip, on_delete):
        super().__init__(timeout=600)
        self.q = q
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
        
        tout = qsq.get_timeout()+10
        if sesObj.settings['moderated']: 
            tout=1500
            
        super().__init__(timeout=tout)
        self.qsq: QuizSessionQuestion = qsq
        self.sesObj = sesObj
        self.question = qsq.question
        self.correct_list = self.question.get_correct_list()
        self.reactions = dict()
        self.over=False
        
        ans = qsq.get_answers()
        if len(ans)>2:
            random.shuffle(ans)
            
        for a in ans:
            self.add_item(
                QuizView.QuizButton(self, qsq, answer=a, correct=a.is_correct())
            )
            
            
    @classmethod 
    def get_question_image(cls, q:Question, overwrite=False):
        name = f"quizfrage_{q.uuid}.png"
        pfad = os.path.join("images", name)
        add_img = None
        if q.has_image():
            add_img = os.path.join("images", q.image)
            
        if not os.path.isfile(pfad) or overwrite:
            return QuizImageGenerator().generate_image(text=q.question, uuid=q.uuid, additional_image_path=add_img)

        return pfad
        
    @classmethod
    def get_question_text(cls, qsq):
        q = qsq.question
        multi = "(Mehrfachauswahl)" if q.is_multiple() else ""
        katstring = ", ".join(q.get_categories())
        qtext = f"# Quizfrage {str(qsq.number)} / {str(qsq.total)}\n### {multi} \n-# Zeit: {str(q.timeout)}s | Kategorie: {katstring} | {q.uuid}"
        return qtext

    @classmethod
    def get_embed(cls, qsq, image_file=None, show_answers=False, no_question=False):
        
        t = ""
        if isinstance(qsq, QuizSessionQuestion):
            q: Question = qsq.question
            t += "Quizfrage " + str(qsq.number) + "/" + str(qsq.total)
        else:
            q: Question = qsq
            t += "Quizfrage"
        
        if q.is_multiple():
            t += "   (Mehrfachauswahl)"
        
        desc = ""
        if not no_question:
            desc = "```"+q.question+"```\n\n"
        
        embed = discord.Embed(title=t, description=desc)

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
            if set(cur_answers) == set(self.correct_list):
                embed.add_field(name="Richtige Antwort!", value="", inline=False)
                embed.color=discord.Color.green()
            else:
                y=max(80-len(str(corr_list)),0)
                padding="."*y
                r = "||" + corr_list+ padding  + " ||"
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
            act=not qsq.is_open()
            super().__init__(label=str(answer), style=discord.ButtonStyle.primary, disabled=act)
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
            


ENTRIES_PER_PAGE = 20

class QuestionPaginator(View):
    def __init__(self, data: list):
        super().__init__(timeout=180)
        self.entries = data
        self.page = 0

        self.prev_button = Button(label="⬅️ Vorherige Seite", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="Nächste Seite ➡️", style=discord.ButtonStyle.primary)
        self.next_button.callback = self.show_next_page
        self.prev_button.callback = self.show_prev_page
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    def generate_page_content(self):
        def truncate(text, length):
            return text[:length - 3].replace("\n","") + "..." if len(text) > length else text

        start = self.page * ENTRIES_PER_PAGE
        end = start + ENTRIES_PER_PAGE
        page_entries = self.entries[start:end]

        total_pages = (len(self.entries) - 1) // ENTRIES_PER_PAGE + 1
        lines = [f"Seite {self.page + 1}/{total_pages}\n\n",  
                 "UUID              | Frage",
                 "------------------|----------------------------------------"]

        for uuid, question in page_entries:
            lines.append(f"{truncate(uuid, 17).ljust(18)}| {truncate(question, 40)}")

        return "```\n" + "\n".join(lines) + "\n```"

    async def show_next_page(self, interaction: discord.Interaction):
        self.page += 1
        max_page = (len(self.entries) - 1) // ENTRIES_PER_PAGE
        if self.page > max_page:
            self.page = 0

        content = self.generate_page_content()
        await interaction.response.edit_message(content=content, view=self)  

    async def show_prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        max_page = (len(self.entries) - 1) // ENTRIES_PER_PAGE
        if self.page > max_page:
            self.page = 0
        if self.page < 0:
            self.page = max_page

        content = self.generate_page_content()
        await interaction.response.edit_message(content=content, view=self)  
        
import os

class PoolPaginator(View):
    def __init__(self, bot:Beep, qlist:list[Question], uuid):
        super().__init__(timeout=300)
        self.qlist:list[Question] = qlist
        self.page = 0
        self.bot:Beep=bot
        
        if uuid:
            for i, wert in enumerate(self.qlist):
                if wert.uuid == uuid:
                    self.page = i
                    break
                
        self.prev_button = Button(label="⬅️ Vorherige Frage", style=discord.ButtonStyle.primary)
        self.show_button = Button(label="🔍 Zeigen", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Nächste Frage ➡️", style=discord.ButtonStyle.primary)
        self.next_button.callback = self.show_next_page
        self.show_button.callback = self.show_question
        self.prev_button.callback = self.show_prev_page
        self.add_item(self.prev_button)
        self.add_item(self.show_button)
        self.add_item(self.next_button)

    def generate_embed(self):
        q:Question = self.qlist[self.page]

        emb = QuizView.get_embed(q, show_answers=True)
        if q.has_image():
            emb.add_field(name="Bild:", value="vorhanden", inline=True)
            
        return emb

    def generate_page_content(self):
        q:Question = self.qlist[self.page]
        total_pages = (len(self.qlist) - 1) 
        lines = f"Frage {self.page + 1}/{total_pages}\n\n"
        
    async def show_question(self, interaction:discord.Interaction):
        q:Question = self.qlist[self.page]
        if not q:
            return
        await self.bot.show_question_now(interaction, q.uuid, interaction.guild.id)
        
    async def show_prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        max_page = (len(self.qlist) - 1) 
        if self.page > max_page or self.page < 0:
            self.page = 0
    
        content = self.generate_page_content()
        embed = self.generate_embed()
        await interaction.response.edit_message(content=content, embed=embed, view=self)  
           
    async def show_next_page(self, interaction: discord.Interaction):
        self.page += 1
        max_page = (len(self.qlist) - 1) 
        if self.page > max_page or self.page < 0:
            self.page = 0

        content = self.generate_page_content()
        embed = self.generate_embed()
        await interaction.response.edit_message(content=content, embed=embed, view=self)  
        
                
          
class KategorieView(discord.ui.View):
    def __init__(self, sesObj: QuizSessionOption, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.ausgewaehlt = []
        self.max_fragen = 10
        self.sesObj = sesObj
        self.beepbot:Beep = sesObj.bot
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
            placeholder="z.B. 10",
            required=True,
            default="10",
            max_length=3
        )

        def __init__(self, parent_view):
            super().__init__()
            self.parent_view: KategorieView = parent_view

        async def on_submit(self, interaction: discord.Interaction):
            try:
                wert = int(self.anzahl.value)
                
                wert = max(1,wert)
                if not self.parent_view.beepbot.usr.check_if_mod(self.parent_view.sesObj.guild, self.parent_view.sesObj.user):
                    wert = min(25,wert)
            
                self.parent_view.max_fragen = wert
                feedback = f"✅ **Maximale Fragen auf {wert} gesetzt!**"
            except ValueError:
                feedback = "❌ **Bitte gib eine gültige positive Zahl ein.**"

            await self.parent_view.update_message(interaction, feedback=feedback)



class ChangeQuizSettingsView(discord.ui.View):
    
    def __init__(self, channel_id, quiz_settings:dict):
        super().__init__(timeout=300)
        self.channel_id = channel_id
        self.quiz_settings:dict=quiz_settings

        for text,feature in zip(QuizSessionOption.FEATURES_TEXT,QuizSessionOption.FEATURES_OPTION):
            if feature=="moderated":
                continue
                
            button = self.FeatureButton(text, feature, self)
            self.add_item(button)

    class FeatureButton(discord.ui.Button):
        def __init__(self, text:str, feature: str, parent):
            self.feature = feature
            self.text = text
            self.parent:ChangeQuizSettingsView = parent
            current_state = self.parent.quiz_settings[feature]
            label = f"{text}: {'✅' if current_state else '❌'}"
            if current_state:
                super().__init__(label=label, style=discord.ButtonStyle.green)
            else:
                super().__init__(label=label, style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            self.parent.quiz_settings[self.feature] = not self.parent.quiz_settings[self.feature]
            await interaction.response.edit_message(view=ChangeQuizSettingsView(self.parent.channel_id, self.parent.quiz_settings))


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
                if feature=="remove_answers":# and not self.beepbot.usr.check_if_mod(sesObj.guild, sesObj.user):
                    continue
                if feature=="remove_question":
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