from datetime import datetime
import hashlib
import asyncio
import base64
import os
import requests
import json


APP_SECRET = ""
HASH_SECRET = ""
BASE_DOMAIN = "beepbot.org"
BASE_URL = "https://"+BASE_DOMAIN
   
class QuizBotException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

 
class WebConnector:
    
    def generate_hourly_hash(self):
        current_hour = datetime.now().strftime("%Y%m%d%H")
        key_string = HASH_SECRET + current_hour
        hash_obj = hashlib.sha256(key_string.encode('utf-8'))
        return hash_obj.hexdigest()


    async def fetch(self, url, params=None):
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, requests.get, url, params)
        return response

    async def load_json(self, code):
        params = {
            "key": APP_SECRET,
            "code": code
        }
        
        response = await self.fetch(BASE_URL + "/load.php", params)
        if response.status_code != 200:
            raise QuizBotException(f"Fehler beim Abrufen der Quiz-Daten: {response.status_code} {response.text}")

        quiz_data = response.json()
        return quiz_data

    async def load_image(self, image_filename):
        params = {
            "key": APP_SECRET,
            "image": image_filename
        }
        response = await self.fetch(BASE_URL + "/load.php", params)
        
        if response.status_code != 200:
            raise QuizBotException(f"Fehler beim Laden des Bildes: {response.status_code} {response.text}")
        return response.content

    async def load_quiz(self, code):
        pos_list = []
        try:
            quiz_data = await self.load_json(code)
            await asyncio.sleep(0)
        except Exception as ex:
            return

        for i, quiz in enumerate(quiz_data):
            if "image" in quiz and quiz["image"].strip() != "":
                try:
                    image_data = await self.load_image(quiz["image"])
                    filename = os.path.join("images",quiz["image"])
                    with open(filename, "wb") as f:
                        f.write(image_data)
                    await asyncio.sleep(0)
                    pos_list.append(quiz)
                except Exception as e:
                    pass
            else:
                pos_list.append(quiz)
        return pos_list
    
    async def send_to_server(self, json_data):
        headers = {"Content-Type": "application/json"}
        response = requests.post(BASE_URL + "/quiz.php?key="+APP_SECRET, data=json.dumps(json_data), headers=headers)
        if response.status_code != 200:
            raise Exception(f"Fehler beim Laden.")
        return response.text
    
    def image_to_json(self, file_name):
        supported_extensions = ['jpg', 'jpeg', 'png', 'gif']

        ext = os.path.splitext(file_name)[1][1:].lower()
        
        if ext not in supported_extensions:
            raise ValueError(f"Dateiendung '{ext}' wird nicht unterstützt. Unterstützt werden: {supported_extensions}")
        
        if ext == 'png':
            mime_type = 'image/png'
        elif ext in ['jpg', 'jpeg']:
            mime_type = 'image/jpeg'
        elif ext == 'gif':
            mime_type = 'image/gif'
        
        with open(os.path.join("images",file_name), 'rb') as image_file:
            encoded_data = base64.b64encode(image_file.read()).decode('utf-8')

        image_data = f"data:{mime_type};base64,{encoded_data}"
        return image_data