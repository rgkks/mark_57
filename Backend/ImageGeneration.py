import requests
import urllib.parse
import os
from time import sleep
from dotenv import dotenv_values
_env = dotenv_values("jarvis.env")
IMAGE_MODEL = _env.get("ImageModel", "flux")
def generate_image(prompt):
    enhanced_prompt = f"{prompt}, 8k resolution, cinematic lighting, masterpiece, highly detailed, high bitrate, clean shadows, smooth gradients, no compression artifacts, 16-bit color depth"
    encoded_prompt = urllib.parse.quote(enhanced_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model={IMAGE_MODEL}&width=1024&height=1024&enhance=true&nologo=true"
    print(f"Generating image from: {url}")
    os.makedirs("Data", exist_ok=True)
    filename = f"Data/{prompt.replace(' ', '_')}.jpg"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Image saved as {filename}")
        else:
            print(f"Failed to generate image. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
try:
    with open("Frontend/Files/ImageGeneration.data", "r") as file:
        Data = file.read()
    Prompt, Status = Data.split(",")
    if Status.strip() == "True":
        print("Generating Image...")
        generate_image(Prompt.strip())
except Exception as e:
    print(f"Error: {e}")
finally:
    with open("Frontend/Files/ImageGeneration.data", "w") as file:
        file.write("False,False")
