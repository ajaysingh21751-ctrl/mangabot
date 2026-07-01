import os
import io
import requests
from telethon import TelegramClient, events
from PIL import Image

# --- SETTINGS ---
API_ID = 32833103          
API_HASH = '9be18d4f7dd2c032e06a1cd2dc0c6629'    
BOT_TOKEN = '8954139735:AAEApjVKyowIez5c0L5IjwOriPuttZPLitE' 

bot = TelegramClient('universal_manga_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

BASE_API = "https://mangadex.org"

# --- HELPER FUNCTIONS ---
def search_manga(title):
    res = requests.get(f"{BASE_API}/manga", params={"title": title, "limit": 5})
    if res.status_code == 200:
        return res.json().get('data', [])
    return []

def get_all_chapters(manga_id):
    # Yeh function ab 100 nahi, balki saare ke saare chapters nikalega (Purane se lekar Naye tak)
    all_chapters = []
    offset = 0
    limit = 100
    
    while True:
        res = requests.get(f"{BASE_API}/manga/{manga_id}/feed", params={
            "translatedLanguage[]": ["en"],
            "limit": limit,
            "offset": offset,
            "order[chapter]": "asc"  # 'asc' karne se purane chapter sabse pehle dikhenge
        })
        if res.status_code != 200:
            break
            
        data = res.json().get('data', [])
        if not data:
            break
            
        all_chapters.extend(data)
        if len(data) < limit:
            break
        offset += limit
        
    return all_chapters

def download_chapter_as_pdf(chapter_id, pdf_path):
    res = requests.get(f"{BASE_API}/at-home/server/{chapter_id}")
    if res.status_code != 200:
        return False
    
    data = res.json()
    base_url = data.get('baseUrl')
    chapter_data = data.get('chapter', {})
    hash_code = chapter_data.get('hash')
    file_names = chapter_data.get('data')
    
    if not file_names or not base_url:
        return False

    images = []
    for file in file_names:
        page_url = f"{base_url}/data/{hash_code}/{file}"
        img_res = requests.get(page_url)
        if img_res.status_code == 200:
            img = Image.open(io.BytesIO(img_res.content)).convert('RGB')
            images.append(img)
            
    if not images:
        return False

    images[0].save(pdf_path, save_all=True, append_images=images[1:])
    return True

# --- TELEGRAM BOT HANDLERS ---

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("👋 Namaste! Main ek Universal Manga Bot hoon.\nManga search karne ke liye type karein:\n`/search [Manga Name]`")

@bot.on(events.NewMessage(pattern='/search (.+)'))
async def search(event):
    query = event.pattern_match.group(1)
    await event.reply(f"🔍 '{query}' ko saare scans par dhoondha ja raha hai...")
    
    mangas = search_manga(query)
    if not mangas:
        await event.reply("❌ Koi manga nahi mila! Kripya naam sahi se check karein.")
        return
        
    text = "**🔍 Search Results:**\n\n"
    for m in mangas:
        m_id = m['id']
        title = m['attributes']['title'].get('en', 'Unknown Title')
        text += f"📖 **{title}**\n👉 Saare Chapters dekhne ke liye click karein: `/chapters_{m_id}`\n\n"
        
    await event.reply(text, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/chapters_(.+)'))
async def list_chapters(event):
    manga_id = event.pattern_match.group(1)
    await event.reply("⏳ Aapke liye saare purane aur naye chapters dhoondhe ja rahe hain, isme thoda time lag sakta hai...")
    
    chapters = get_all_chapters(manga_id)
    if not chapters:
        await event.reply("❌ Is manga ke koi chapters nahi mile.")
        return
        
    await event.reply(f"📚 Kul milakar {len(chapters)} chapters mile hain! List bheji ja rahi hai...")
    
    # Telegram ki ek message limit hoti hai, isliye hum 40-40 ke tukdo me list bhejenge
    text = "**📚 ALL CHAPTERS LIST (Purane se Naye):**\n\n"
    for count, ch in enumerate(chapters, 1):
        ch_id = ch['id']
        ch_num = ch['attributes']['chapter'] or count
        ch_title = ch['attributes']['title'] or f"Chapter {ch_num}"
        text += f"📥 Ch {ch_num} - {ch_title}\nDownload: `/dl_{ch_id}`\n\n"
        
        if count % 40 == 0:
            await event.reply(text, parse_mode='markdown')
            text = ""
            
    if text:
        await event.reply(text, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/dl_(.+)'))
async def download(event):
    chapter_id = event.pattern_match.group(1)
    status_msg = await event.reply("⏳ Saare scans se pages scrape kiye ja rahe hain aur PDF banayi ja rahi hai. Kripya 1-2 minute intezar karein...")
    
    pdf_filename = f"Manga_Chapter_{chapter_id}.pdf"
    
    try:
        success = download_chapter_as_pdf(chapter_id, pdf_filename)
        if not success:
            await status_msg.edit("❌ Pages download karne me error aaya.")
            return
            
        await status_msg.edit("🚀 PDF taiyar hai! Telegram par upload ho raha hai...")
        
        await event.client.send_file(
            event.chat_id, 
            pdf_filename, 
            caption="✅ Aapka chapter taiyar hai! Happy Reading!"
        )
        
        if os.path.exists(pdf_filename):
            os.remove(pdf_filename)
            
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit(f"⚠️ Error: {str(e)}")
        if os.path.exists(pdf_filename):
            os.remove(pdf_filename)

print("⚡ Bot live ho gaya hai...")
bot.run_until_disconnected()
