import asyncio
import os
import json
import sys
import requests
from datetime import datetime, timedelta
import discord
from discord import app_commands

# ================= [ 환경 설정 항목 ] =================
# 기상청 API 인증키 (디코딩 키)
DECODING_KEY = "2689897bb5c5e95749a280dd0afb4f85565d024f393ee4279fa4ba41f8e8fe49"
USER_DATA_FILE = "users.json"

# 지원하는 지역 좌표 맵
LOCATION_MAP = {
    "김포": {"nx": 55, "ny": 128},
    "서울": {"nx": 60, "ny": 127},
    "인천": {"nx": 55, "ny": 124},
    "부산": {"nx": 98, "ny": 76},
}
# ====================================================

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_weather(nx, ny):
    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
    
    now = datetime.now()
    if now.minute < 40:
        target_time = now - timedelta(hours=1)
    else:
        target_time = now
        
    base_date = target_time.strftime("%Y%m%d")
    base_time = target_time.strftime("%H00")
    
    params = {
        "serviceKey": DECODING_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": str(nx),
        "ny": str(ny)
    }
    
    try:
        response = requests.get(url, params=params, verify=True)
        if response.status_code == 200:
            try:
                res_json = response.json()
                items = res_json['response']['body']['items']['item']
                weather_data = {}
                for item in items:
                    weather_data[item['category']] = float(item['obsrValue'])
                return weather_data
            except KeyError:
                print(f"❌ 기상청 데이터 오류: {response.text}")
                return None
    except Exception as e:
        print(f"❌ 파싱 에러: {e}")
    return None

def make_weather_embed(location_name, weather):
    temp = weather.get("T1H", 0.0)
    humidity = weather.get("REH", 0)
    rain_type = int(weather.get("PTY", 0))
    wind = weather.get("WSD", 0.0)
    
    pty_dict = {0: "맑음 ☀️", 1: "비 🌧️", 2: "비/눈 🌨️", 3: "눈 ❄️", 5: "빗방울 💧"}
    weather_status = pty_dict.get(rain_type, "맑음 ☀️")

    embed = discord.Embed(title=f"📍 실시간 {location_name} 날씨 알림", color=0x5865F2)
    embed.add_field(name="현재 상태", value=weather_status, inline=True)
    embed.add_field(name="현재 기온", value=f"{temp}°C", inline=True)
    embed.add_field(name="현재 습도", value=f"{humidity}%", inline=True)
    embed.add_field(name="현재 풍속", value=f"{wind}m/s", inline=True)
    embed.set_footer(text=f"기상청 실황 데이터 | 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return embed

class WeatherBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = WeatherBot()

@client.tree.command(name="동네설정", description="날씨를 받아볼 동네를 처음으로 지정합니다.")
@app_commands.describe(동네이름="동네 이름을 입력하세요 (예: 김포, 서울, 인천, 부산)")
async def set_location(interaction: discord.Interaction, 동네이름: str):
    user_id = str(interaction.user.id)
    user_data = load_user_data()
    
    if 동네이름 in LOCATION_MAP:
        user_data[user_id] = {
            "name": 동네이름,
            "nx": LOCATION_MAP[동네이름]["nx"],
            "ny": LOCATION_MAP[동네이름]["ny"]
        }
        save_user_data(user_data)
        await interaction.response.send_message(f"✅ 동네가 **{동네이름}**(으)로 등록되었습니다!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ '{동네이름}'은 지원하지 않는 지역입니다. (김포, 서울, 인천, 부산 중 선택)", ephemeral=True)

@client.tree.command(name="지역변경", description="기존에 설정한 날씨 알림 지역을 변경합니다.")
@app_commands.describe(새동네이름="새롭게 변경할 동네 이름을 입력하세요 (예: 김포, 서울, 인천, 부산)")
async def change_location(interaction: discord.Interaction, 새동네이름: str):
    user_id = str(interaction.user.id)
    user_data = load_user_data()
    
    if user_id not in user_data:
        await interaction.response.send_message("❌ 등록된 지역 정보가 없습니다. 먼저 `/동네설정` 명령어를 사용해 주세요!", ephemeral=True)
        return

    if 새동네이름 in LOCATION_MAP:
        old_location = user_data[user_id]["name"]
        user_data[user_id] = {
            "name": 새동네이름,
            "nx": LOCATION_MAP[새동네이름]["nx"],
            "ny": LOCATION_MAP[새동네이름]["ny"]
        }
        save_user_data(user_data)
        await interaction.response.send_message(f"🔄 날씨 알림 지역이 **{old_location}** ➡️ **{새동네이름}**(으)로 성공적으로 변경되었습니다!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ '{새동네이름}'은 지원하지 않는 지역입니다. (김포, 서울, 인천, 부산 중 선택)", ephemeral=True)

@client.tree.command(name="날씨", description="등록한 동네의 현재 날씨를 실시간으로 가져옵니다.")
async def send_weather_now(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = load_user_data()
    
    if user_id not in user_data:
        await interaction.response.send_message("❌ 먼저 `/동네설정` 명령어로 동네를 등록해 주세요!", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    info = user_data[user_id]
    weather = get_weather(info["nx"], info["ny"])
    
    if not weather:
        await interaction.followup.send("❌ 실시간 기상청 데이터를 가져오지 못했습니다.")
        return
        
    embed = make_weather_embed(info["name"], weather)
    try:
        await interaction.user.send(embed=embed)
        await interaction.followup.send("📬 최신 날씨 정보를 개인 DM으로 전송했습니다!", ephemeral=True)
    except:
        await interaction.followup.send("❌ DM을 보낼 수 없습니다. 봇과 같은 서버에 있는지 확인해 주세요.", ephemeral=True)

@client.event
async def on_ready():
    print(f"🤖 {client.user} 봇 정상 작동 시작...")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--cron":
        print("⏰ 예약 작업 가동: 등록된 유저들에게 일괄 DM 전송을 시작합니다.")
        user_data = load_user_data()
        for user_id, info in user_data.items():
            weather = get_weather(info["nx"], info["ny"])
            if weather:
                try:
                    user = await client.fetch_user(int(user_id))
                    embed = make_weather_embed(info["name"], weather)
                    await user.send(embed=embed)
                    print(f"✅ 유저 {user_id} ({info['name']}) 전송 완료")
                except Exception as e:
                    print(f"❌ 유저 {user_id} 전송 실패: {e}")
        await client.close()

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ 에러: BOT_TOKEN 환경 변수를 찾을 수 없습니다. GitHub Secrets 설정을 확인해 주세요.")
        sys.exit(1)
        
    asyncio.run(client.start(BOT_TOKEN))