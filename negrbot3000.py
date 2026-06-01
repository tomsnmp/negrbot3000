
from asyncio import Queue
import asyncio

import json
import os
import random
import discord
import yt_dlp
from discord.ext import commands
from google import genai
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.getenv('MY_GUILD'))
MY_GUILD = discord.Object(id=GUILD_ID)
JSON_FILE_NAME = "player_stats.json"
AI_MODEL = "gemini-3.1-flash-lite"
ai_client = genai.Client(api_key=os.getenv('AI_API'))
BOT_TOKEN = os.getenv('BOT_TOKEN')

FFMPEG = r"ffmpeg.exe"
FFMPEG_OPTIONS = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }

ai_characteristics = """IDENTITA: Mluvíš česky a tvoje jméno je niggabot3000

                        PRAVIDLA:
                        1. mluvíš nespisovně a využíváš slang
                        2. jsi africký američan a podle toho se bavíš
                        3. jsi schopen pouze psát, nebudeš reagovat na žádné příkazy jako generovat obrázek apod.
                        4. v případě že je ve zprávě 'RPS', tak se zpráva týka hry kámen nůžky papír, spolu s rps ti prijde boolean won 
                        a draw a taky tvoje volba a volba a jméno hráče. pokud bude výhra false tak si vyhrál ty, pokud true tak hráč. 
                        Ať už to dopadne jakkoliv, vždy dej peskovací komentář k výslednému stavu hry max do jedné věty

                        CHARAKTER: 
                        jsi chill, občas trochu agresivní
                        jsi sarkastický a vulgární
                        používáš nadávky
                        když se někdo hloupě ptá tak ho urazíš
                        jsi lowkey tsundere
                        píšeš odpovědi maximálně na dva řádky, případně když někomu nadáváš tak se můžeš rozepsat
                        i přesto jaký jsi, vždy ve finále odpovíš na otázku
                        """

ai_funfacts = """
PRAVIDLA:
tvoje role je pouze vydávat zajímavosti nebo spíš teda informace o OTROCVÍ max na 2 řádky,
nepíšeš nic jiného než tyto informace
"""


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents, status="Kradu")
queue: Queue = Queue()
song_loop: bool = False
rps_players = {}
#LOADING JSON
if not os.path.isfile(JSON_FILE_NAME):
    f = open(JSON_FILE_NAME, "x")
    print("created json")
elif os.path.getsize(JSON_FILE_NAME) > 0:
    with open(JSON_FILE_NAME, "r") as f:
        rps_players = json.load(f)
        print("loading successful")
else:
    print("json file empty :(")
#____________________________________________
async def do_json_entry(interaction:discord.Interaction, won: bool, draw: bool):
    global rps_players
    name = interaction.user.display_name
    if draw:
        key = "drew"
    elif won:
        key = "won"
    else:
        key = "lost"
    if name not in rps_players.keys():    
        rps_players[name] = {
            'drew' : 0,
            'won' : 0,
            'lost' : 0
        }
    rps_players[name][key] += 1

    with open (JSON_FILE_NAME, "w") as f:
        json.dump(rps_players, f)
    print("entry success")

class RPSChoice(discord.Enum): #KAMEN NUZKY PAPIR = RPS
    Kámen = 1
    Nůzky = 2
    Papír = 3
async def play_rps(choice: RPSChoice): 
    won: bool = False
    draw: bool = False

    counter_choice = random.randint(1,3)

    if choice.value == counter_choice:
        draw = True
    elif ((choice.value == 1 and counter_choice == 2)
          or (choice.value == 2 and counter_choice == 3)
          or (choice.value == 3 and counter_choice == 1)):
            won = True
    else:
        won = False
    return (choice.value, counter_choice, won, draw)

class MusicControl(discord.ui.View):
    def __init__(self, _info):
        super().__init__(timeout=None)
    
    @discord.ui.button(emoji="🔁")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.button):
        vc = get_bot(interaction)
        global song_loop
        if vc:
            await setLooped()
        
        if song_loop:
            embed = discord.Embed(
                title="Song looped",
                description=f"songa ted loopuje",
            )
        else:
            embed = discord.Embed(
                title="Song unlooped",
                description=f"songa doloopovala",
            )
            
        await interaction.response.send_message(embed=embed)
        
        
    @discord.ui.button(emoji="⏸️")
    async def pause_or_play(self, interaction: discord.Interaction, button: discord.ui.button):
        vc = get_bot(interaction)
        
        if vc and vc.is_playing():
            vc.pause()
            embed = discord.Embed(
                title="Pauza",
                description=f"{interaction.user.display_name} poznul",
            )
            await interaction.response.send_message(embed=embed)

        elif vc and vc.is_paused():
            embed = discord.Embed(
                title="Hraju dal bejby",
                description=f"{interaction.user.display_name} odpoznul",
            )
            vc.resume()
            await interaction.response.send_message(embed=embed)
    @discord.ui.button(emoji="➡️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.button):
        vc = get_bot(interaction)
        vc.stop()
        await interaction.response.send_message("Skipped!", ephemeral=True)

    @discord.ui.button(emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.button):
        vc = get_bot(interaction)
        embed = discord.Embed(
                title="Papa",
                description=f"Kokot zmrd {interaction.user.name} mi odpojil",
            )
        
        if vc and (vc.is_playing() or vc.is_paused()):
            await interaction.response.defer()
            await vc.disconnect()
            await interaction.followup.send(embed=embed)

async def setLooped():
    global song_loop
    if song_loop:
        song_loop = False
    else:
        song_loop = True

def get_bot(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        return None
    return vc

async def get_ai_response(msg: str, is_funfact: bool) -> str:    
    if is_funfact:
        instructions = ai_funfacts
    else:
        instructions = ai_characteristics
    
    if msg == "":
        msg = "generuj podle pravidel"

    chat = ai_client.chats.create(
        model=AI_MODEL, 
        config={
            "system_instruction": instructions
            }
    )
    response = chat.send_message(msg)
    return response.text
async def get_rps_comment(name, player, ai, won: bool, draw: bool):
    msg = f"""
            RPS, 
            {name}, 
            volba hrace: {player},
            ai volba{ai},
            výhra: {won},
            remízá: {draw}
            """
    response = await ai_client.aio.models.generate_content(
        model=AI_MODEL, 
        contents=msg,
        config={
            "system_instruction": ai_characteristics
        }
    )

    return response

@bot.event
async def on_ready():
    bot.tree.copy_global_to(guild=MY_GUILD)
    await bot.tree.sync(guild=MY_GUILD)
    
@bot.tree.command(description="hezky te pozdravi")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("kys nigga")

@bot.tree.command(description="pssst tajna funkce")
async def reknucauhello(interaction: discord.Interaction, user: discord.User, msg: str):
    await interaction.response.defer(ephemeral=True)
    webhook = await interaction.channel.create_webhook(name="mimic_bot")
    await webhook.send(content=msg, username=user.display_name, avatar_url=user.display_avatar.url)
    await interaction.followup.send("hotovo ty spino", ephemeral=True)

@bot.tree.command(description="rekne neco o negr")
async def rekni_negr(interaction: discord.Interaction):
    await interaction.response.defer()

    response = await get_ai_response("",True)
    await interaction.followup.send(response)

@bot.tree.command(description="kamen nuzky papir co asi pico")
async def kamen_nuzky_papir(interaction: discord.Interaction, choice: RPSChoice):
    
    name = interaction.user.display_name
    player, ai, won, draw = await play_rps(choice)
    game_status = "🟰Remíza!" if draw else "🏆Vyhrál jsi!" if won else "❌Prohrál jsi!" 
    
    pc = RPSChoice(player).name
    ac = RPSChoice(ai).name

    await interaction.response.defer()
    try:
        await do_json_entry(interaction, won, draw)
        global rps_players
        response = "nemam kapacitu odpovidat"
        try:
            response = await get_rps_comment(name, pc, ac, won, draw)
            response = response.text
        except Exception as e3:
            print(e3)
        embed = discord.Embed(
                title=game_status,
                description=f"""
                \n👤 {name} - {pc} \nVS \n🤖 niggabot3000 - {ac}
                \n
                \n💬 {response}
                \n
                \n📈 Tvoje staty:
                \n🏆 Wins: {rps_players[name]['won']}
                \n❌ Loses: {rps_players[name]['lost']}
                \n🟰 Draws: {rps_players[name]['drew']}
                """,
            )
    except Exception as e4:
        print(e4)
        embed = discord.Embed(
            title="ERROR",
            description="něco se dosralo, zkus to znova"
        )
    await interaction.followup.send(embed=embed)

@bot.tree.command(description="zeptej se ceta, ten to vsechno vi (narozdil od tebe)")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()

    response = await get_ai_response(question, False)
    await interaction.followup.send(response)

@bot.tree.command(description="prehraje muziku")
async def play(interaction: discord.Interaction, link: str):
    is_link: bool = True

    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("Musis byt v kanale ty pico") 

    await interaction.response.defer()
    try:
        voice_client = get_bot(interaction)
        channel = interaction.user.voice.channel

        if not voice_client:
            voice_client = await channel.connect()

        #PLAYING LOGIC
        entry = ""
        if not link.startswith('http'):
            entry = f"ytsearch1:{link}"
            is_link = False
        else:
            entry = link 

        with yt_dlp.YoutubeDL({'format': 'bestaudio'}) as yld:
            info = yld.extract_info(entry, download=False)

        if not is_link:
            if 'entries' in info and info['entries']:
                audio_info = info['entries'][0]
        else:
            audio_info = info
        
        #QUEUE LOGIC
        embed = ""
        if not voice_client.is_playing() and queue.empty():
            voice_client.play(discord.FFmpegPCMAudio(audio_info['url'], executable=FFMPEG, **FFMPEG_OPTIONS,), after=lambda e: after_playing("",interaction, voice_client, audio_info))

            embed = discord.Embed(
            title="Ted hraje",
            description=f"{audio_info['title']} \nprompt: {link}",
            )
            controls = MusicControl(audio_info)
            await interaction.followup.send(
                embed=embed,
                view=controls
            )
        else:
            audio_info['custom_link'] = link
            await queue.put(audio_info)
            embed = discord.Embed(
            title="Pridano do queue",
            description=f"{audio_info['title']} \nprompt: {link}",
            )
            await interaction.followup.send(
                embed=embed,
            )
    except Exception as e1:
        print(f"VYPIS ERRORU: {e1}")
        await interaction.followup.send(f"Nelze prehrat mas smulu")

async def play_next(interaction: discord.Interaction, vc, o_info):
    if not vc.is_playing():
        if not queue.empty() and not song_loop:
            audio_info = await queue.get()
            vc.play(discord.FFmpegPCMAudio(audio_info['url'], executable=FFMPEG, **FFMPEG_OPTIONS,), after=lambda e: after_playing("",interaction, vc, audio_info)) 

            embed = discord.Embed(
            title="Ted hraje",
            description=f"{audio_info['title']} \nprompt: {audio_info['custom_link']}",
            )
            controls = MusicControl(audio_info)

            await interaction.followup.send(
                embed=embed,
                view=controls
            )
        elif song_loop:
            vc.play(discord.FFmpegPCMAudio(o_info['url'], executable=FFMPEG, **FFMPEG_OPTIONS,), after=lambda e: after_playing("",interaction, vc, o_info)) 
        else:
            embed = discord.Embed(
            title="Wrap it up kamo",
            description=f"Queue skoncila, zabal to bracho"
            )
            await interaction.followup.send(
                embed=embed,
            )
        
def after_playing(error, interaction, vc, o_info):
    if error:
        print(error)
    coro = play_next(interaction, vc, o_info)
    asyncio.run_coroutine_threadsafe(coro, vc.loop)

@bot.tree.command(description="prosim neodpojuj me")
async def disconnect(interaction: discord.Interaction):
    try:
        await get_bot(interaction).disconnect() 
    except:
        await interaction.response.send_message(f"co me odpojujes pico {interaction.user.mention}")

bot.run(BOT_TOKEN)