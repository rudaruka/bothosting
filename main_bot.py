import discord
from discord.ext import commands
import os
import math
import pickle # Python 객체를 파일로 저장하고 불러오기 위한 라이브러리
import asyncio # 비동기 작업을 위한 라이브러리

# ----------------------------------------------------------------------
# 🚨🚨🚨 사용자 설정 필수 영역 🚨🚨🚨
# ----------------------------------------------------------------------

# 1. 임시 채널 시스템 관련 설정
# 🚨 확인 완료: 이 ID (1450345043390107730)가 실제 서버의 트리거 채널 ID와 일치하는지 다시 확인해주세요. 
CREATE_CHANNEL_ID = 1450363133431517224 

# 2. 봇 토큰 설정 
acess_token = os.environt["BOT_TOKEN"]
client.run(acess_token)

# 3. 경고 시스템 및 명령어 관련 설정
WARNING_FILE = 'warnings.pkl' 
ALLOWED_ROLES = ["방장", "부방장"] # 경고 시스템 명령어에만 적용됩니다.
# ----------------------------------------------------------------------

# --- 전역 변수 및 초기화 ---
warning_data = {} 
temporary_channels = set() 

# 커스텀 색상 (HEX)
COLOR_ORANGE = 0xFF6600 
COLOR_BLUE = 0x4D94FF 
COLOR_REPORT = 0x992D2D 
COLOR_FINAL_WARNING = 0x2C2F33 

# 봇 권한(Intent) 설정
intents = discord.Intents.default()
intents.members = True       # 멤버 정보
intents.message_content = True # 명령어 처리
intents.voice_states = True  # 임시 채널 관리

BOT_PREFIX = "!"
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


# --- 데이터 영구 저장 함수 ---

def load_warnings():
    """warnings.pkl 파일에서 데이터를 불러옵니다."""
    global warning_data
    if os.path.exists(WARNING_FILE):
        with open(WARNING_FILE, 'rb') as f:
            try:
                warning_data = pickle.load(f)
                if not isinstance(warning_data, dict):
                    raise TypeError("불러온 데이터가 딕셔너리 형태가 아닙니다.")
                print(f"✅ 경고 데이터 {len(warning_data)}개 로드 완료.")
            except (EOFError, pickle.UnpicklingError, TypeError):
                print("⚠️ 경고 파일이 손상되었거나 비어 있습니다. 새 데이터로 시작합니다.")
                warning_data = {}
    else:
        print("💡 경고 파일이 없습니다. 새로 생성합니다.")
        warning_data = {}

def save_warnings():
    """현재 경고 데이터를 warnings.pkl 파일에 저장합니다."""
    with open(WARNING_FILE, 'wb') as f: 
        pickle.dump(warning_data, f)


# --- 봇 이벤트 핸들러 (통합) ---

@bot.event
async def on_ready():
    """봇이 준비되었을 때 실행됩니다."""
    load_warnings() # 경고 데이터 로드
    print(f'봇 이름: {bot.user.name}')
    print(f'봇 ID: {bot.user.id}')
    print(f'*** 현재 설정된 CREATE_CHANNEL_ID: {CREATE_CHANNEL_ID} ***')
    print('봇이 성공적으로 준비되었습니다.')
    
    await bot.change_presence(activity=discord.Game(name=f"{BOT_PREFIX}경고확인 | 임시채널 관리 중"))

@bot.event
async def on_command_error(ctx, error):
    """명령어 실행 중 오류 발생 시 처리합니다."""
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send(f"🚨 **권한 부족:** 이 명령어는 `{', '.join(ALLOWED_ROLES)}` 중 하나의 역할만 사용할 수 있습니다.", delete_after=10)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("👤 **오류:** 해당 사용자를 찾을 수 없습니다. 사용자 멘션(예: @사용자이름)을 정확히 입력해주세요.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ **잘못된 입력:** 입력 형식이 올바르지 않습니다. `!경고추가 @사용자 3` 또는 `!경고삭제 @사용자 1` 형식으로 입력해주세요.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"명령어 오류 발생 ({ctx.command}): {error}")

@bot.event
async def on_voice_state_update(member, before, after):
    """임시 채널 관리 로직: 채널 생성 및 삭제를 담당합니다."""
    
    # 1. 채널 생성 로직 (사용자가 'Join to Create' 채널에 들어왔을 때)
    if after.channel:
        
        # 💡 디버그: 모든 채널 이동 시도를 기록합니다.
        print(f"[디버그] {member.display_name}이(가) 채널 {after.channel.name} ({after.channel.id})로 이동 시도.")
        
        # 🚨 중요: ID 비교 🚨
        if after.channel.id == CREATE_CHANNEL_ID:
            print("[디버그] ✅ CREATE_CHANNEL_ID 트리거 성공! 채널 생성 로직 실행.")

            # 봇의 채널 관리 권한 확인 (가장 흔한 문제)
            if not member.guild.me.guild_permissions.manage_channels or \
               not member.guild.me.guild_permissions.move_members:
                print(f"[CRITICAL ERROR] 🚨 권한 부족: 봇에 '채널 관리' 또는 '멤버 이동' 권한이 부족합니다. 서버 설정에서 봇 역할의 권한을 확인해주세요.")
                return

            channel_name = f"🎧 {member.display_name}의 채널"
            
            try:
                # 1. 새 음성 채널 생성
                new_channel = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=after.channel.category, # 트리거 채널과 같은 카테고리에 생성
                    reason=f"임시 채널 생성 - 요청자: {member.display_name}"
                )
                
                temporary_channels.add(new_channel.id)
                print(f"[생성] 🚀 임시 채널 '{new_channel.name}' (ID: {new_channel.id}) 생성됨.")

                # 2. 사용자를 새 채널로 이동
                await member.move_to(new_channel)
                print(f"[이동] ➡️ {member.display_name}을(를) 새 채널로 이동 완료.")
                
            except discord.Forbidden as f_err:
                # Forbidden 오류는 권한 부족을 의미합니다.
                print(f"[CRITICAL ERROR] ❌ Discord Forbidden (권한 오류): 채널 생성 또는 이동에 실패했습니다. 상세: {f_err}")
            except Exception as e:
                # 기타 오류 처리
                print(f"[오류] ⚠️ 채널 생성 및 이동 중 예상치 못한 일반 오류 발생: {type(e).__name__}: {e}")
            
    # 2. 채널 삭제 로직 (사용자가 채널을 떠나 채널이 비었을 때)
    if before.channel:
        channel_to_check = before.channel
        
        # 봇이 생성한 임시 채널이고, 멤버 수가 0이며, 트리거 채널 자체가 아닐 때
        if channel_to_check.id in temporary_channels and \
           len(channel_to_check.members) == 0 and \
           channel_to_check.id != CREATE_CHANNEL_ID:
            
            # 짧은 지연 시간 후 확인 및 삭제
            await asyncio.sleep(0.1) 
            
            channel_after_wait = bot.get_channel(channel_to_check.id)
            if channel_after_wait and len(channel_after_wait.members) == 0:
                try:
                    # 채널 삭제
                    await channel_to_check.delete(reason="사용자가 모두 퇴장하여 임시 채널 삭제")
                    
                    temporary_channels.remove(channel_to_check.id)
                    print(f"[삭제] 임시 채널 '{channel_to_check.name}' (ID: {channel_to_check.id}) 삭제됨.")
                    
                except discord.Forbidden:
                    print(f"[오류] 채널 삭제 권한이 없습니다: {channel_to_check.name}")
                except Exception as e:
                    print(f"[오류] 채널 삭제 중 오류 발생: {e}")


# --- 경고 관리 명령어 (기존 명령어, 권한 필요) ---

@bot.command(name="경고추가", help="특정 사용자에게 경고 횟수를 누적하여 추가합니다. (!경고추가 @멘션 추가할_횟수)")
@commands.has_any_role(*ALLOWED_ROLES)
async def add_warning(ctx, member: discord.Member, added_count: int):
    """사용자에게 경고를 누적하여 추가하고 저장합니다."""
    if added_count <= 0:
        await ctx.send("추가하려는 경고 횟수는 1 이상이어야 합니다. 경고 횟수를 줄이려면 `!경고삭제`를 사용하세요.")
        return

    current_count = warning_data.get(member.id, 0)
    new_count = current_count + added_count
    
    warning_data[member.id] = new_count
    save_warnings() # 변경된 데이터 저장

    # 임베드 디자인
    embed = discord.Embed(
        title="🚨 경고 추가 완료",
        description=f"처리자: {ctx.author.mention}",
        color=discord.Color(COLOR_ORANGE)
    )
    embed.add_field(name="대상 사용자", value=member.mention, inline=False)
    embed.add_field(name="추가 전 경고 횟수", value=f"{current_count}개", inline=True)
    embed.add_field(name="추가된 횟수", value=f"+{added_count}개", inline=True)
    embed.add_field(name="최종 경고 횟수", value=f"**{new_count}개**", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"ID: {member.id} | 처리 일시")
    
    await ctx.send(embed=embed)


@bot.command(name="경고삭제", help="특정 사용자의 경고 횟수를 차감합니다. (!경고삭제 @멘션 횟수)")
@commands.has_any_role(*ALLOWED_ROLES)
async def remove_warning(ctx, member: discord.Member, count: int):
    """사용자의 경고 횟수를 차감하고 저장합니다."""
    if count <= 0:
        await ctx.send("차감하려는 경고 횟수는 1 이상이어야 합니다.")
        return

    current_count = warning_data.get(member.id, 0)
    new_count = max(0, current_count - count)
    
    warning_data[member.id] = new_count
    save_warnings() # 변경된 데이터 저장

    # 임베드 디자인
    embed = discord.Embed(
        title="✨ 경고 차감 완료",
        description=f"관리자: {ctx.author.display_name} 님이 처리했습니다.",
        color=discord.Color(COLOR_BLUE)
    )
    embed.add_field(name="대상 사용자", value=member.mention, inline=True)
    embed.add_field(name="차감 횟수", value=f"-{count}개", inline=True)
    embed.add_field(name="최종 경고 횟수", value=f"**{new_count}개**", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"처리 일시")
    
    await ctx.send(embed=embed)


@bot.command(name="경고확인", help="특정 사용자의 현재 경고 횟수를 모두에게 표시합니다. (!경고확인 @멘션)")
@commands.has_any_role(*ALLOWED_ROLES)
async def check_warning(ctx, member: discord.Member):
    """특정 사용자의 경고 횟수를 확인합니다."""
    
    count = warning_data.get(member.id, 0)
    
    # 경고 횟수에 따른 색상 및 메시지 설정
    if count >= 5:
        color = discord.Color(COLOR_FINAL_WARNING)
        status_message = "⚫ **최종 경고!!** 이 사용자는 **추방 대상**입니다. 즉시 조치하세요."
    elif count >= 3:
        color = discord.Color.dark_red()
        status_message = "🔥 **위험:** 경고 횟수가 높습니다. 조치가 필요할 수 있습니다."
    elif count > 0:
        color = discord.Color.gold()
        status_message = "⚠️ **주의:** 경고 횟수를 확인하세요."
    else:
        color = discord.Color.green()
        status_message = "✅ **양호:** 현재 부여된 경고가 없습니다."

    # 임베드 디자인
    embed = discord.Embed(
        title="🔎 사용자 경고 현황 보고서",
        color=color
    )
    
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name="현재 경고 횟수", value=f"**{count}개**", inline=True)
    embed.add_field(name="상태 진단", value=status_message, inline=False)
    
    embed.set_footer(text=f"조회 요청자: {ctx.author.display_name} | ID: {member.id}")
    
    await ctx.send(embed=embed)


@bot.command(name="전체경고", help="현재 경고가 있는 모든 사용자 목록을 확인합니다. (!전체경고)")
@commands.has_any_role(*ALLOWED_ROLES)
async def all_warnings(ctx):
    """경고가 1회 이상 부여된 모든 사용자 목록을 보여줍니다."""
    
    # 경고 횟수가 0보다 큰 사용자만 필터링
    active_warnings = {
        user_id: count 
        for user_id, count in warning_data.items() 
        if count > 0
    }
    
    if not active_warnings:
        embed = discord.Embed(
            title="✨ 서버 전체 경고 현황",
            description="현재 경고가 부여된 사용자가 없습니다. 서버가 매우 평화롭습니다! 🕊️",
            color=discord.Color.green()
        )
        return await ctx.send(embed=embed)

    
    # 경고 횟수 기준 내림차순 정렬
    sorted_warnings = sorted(active_warnings.items(), key=lambda item: item[1], reverse=True)
    
    member_list = []
    
    for user_id, count in sorted_warnings:
        member = ctx.guild.get_member(user_id)
        
        name_display = member.display_name if member else f"알 수 없는 사용자 (ID: {user_id})"
        
        # 5개 이상일 때 검정색 이모티콘 처리
        if count >= 5:
            emoji = "⚫"
        elif count >= 3:
            emoji = "🔴"
        else:
            emoji = "🟠"
        
        member_list.append(f"{emoji} **{count}개** - {name_display}")
        
    list_text = "\n".join(member_list)
    
    # 임베드 디자인
    embed = discord.Embed(
        title=f"📊 서버 전체 경고 리포트",
        description=f"총 {len(active_warnings)}명이 경고 1회 이상을 보유하고 있습니다. (경고 횟수 기준 내림차순)",
        color=discord.Color(COLOR_REPORT)
    )
    
    embed.add_field(name="사용자 현황 (횟수 - 이름)", value=list_text[:1024], inline=False)
    
    embed.set_footer(text=f"총 관리 인원: {len(warning_data)}명 | 조회 요청자: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


# --- 임시 채널 관리 명령어 (채널 이름 변경 권한 개방) ---

@bot.command(name='임시채널목록', help='봇이 현재 관리하는 임시 채널 목록을 표시합니다. (!임시채널목록)')
@commands.has_any_role(*ALLOWED_ROLES) # 관리자만 볼 수 있도록 권한 유지
async def list_temp_channels(ctx):
    """현재 봇이 추적하는 임시 채널 목록을 출력합니다."""
    if not temporary_channels:
        await ctx.send("현재 봇이 관리하는 임시 채널이 없습니다.")
        return

    # 서버에 존재하는 채널 객체만 필터링하여 목록을 만듭니다.
    channel_names = [
        ctx.guild.get_channel(channel_id).name
        for channel_id in temporary_channels
        if ctx.guild.get_channel(channel_id) is not None
    ]

    if not channel_names:
        await ctx.send("현재 서버에서 활성화된 임시 채널이 없습니다.")
        return
        
    response = "--- 현재 활성 임시 채널 ---\n" + "\n".join(channel_names)
    await ctx.send(response)
    
    
@bot.command(name='채널이름변경', help='현재 접속한 임시 채널의 이름을 변경합니다. (채널 내 누구나 사용 가능) (!채널이름변경 새 채널 이름)')
# 🚨🚨🚨 commands.has_any_role(*ALLOWED_ROLES) 데코레이터를 제거했습니다. 🚨🚨🚨
async def rename_temp_channel(ctx, *, new_name: str):
    """현재 사용자가 속한 임시 채널의 이름을 변경합니다. (누구나 사용 가능)"""
    
    # 1. 사용자가 음성 채널에 있는지 확인
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("🚨 **오류:** 채널 이름을 변경하려면 먼저 음성 채널에 접속해야 합니다.", delete_after=10)
        return
        
    current_channel = ctx.author.voice.channel
    
    # 2. 현재 채널이 봇이 관리하는 임시 채널인지 확인
    if current_channel.id not in temporary_channels:
        await ctx.send("🚨 **오류:** 현재 채널은 봇이 관리하는 임시 채널이 아닙니다. 봇이 생성한 채널에서만 이름을 변경할 수 있습니다.", delete_after=10)
        return

    # 3. 채널 이름 변경 시도
    try:
        # discord.VoiceChannel.edit()을 사용하여 이름 변경
        await current_channel.edit(name=new_name, reason=f"사용자({ctx.author.display_name})가 임시 채널 이름 변경")
        
        embed = discord.Embed(
            title="✅ 채널 이름 변경 완료",
            description=f"**변경 전:** {current_channel.name}\n**변경 후:** **{new_name}**",
            color=discord.Color(COLOR_BLUE)
        )
        embed.set_footer(text=f"처리자: {ctx.author.display_name}")
        await ctx.send(embed=embed)
        print(f"[변경] 임시 채널 (ID: {current_channel.id}) 이름이 '{new_name}'으로 변경됨.")
        
    except discord.Forbidden:
        # 이 오류가 발생하면, 봇 자체에 '채널 관리' 권한이 없다는 뜻이므로, 
        # 서버 관리자가 봇 역할에 권한을 부여해야 합니다.
        await ctx.send("🚨 **권한 부족:** 봇에 '채널 관리(Manage Channels)' 권한이 없어 이름을 변경할 수 없습니다. 서버 설정을 확인해주세요.", delete_after=10)
    except Exception as e:
        await ctx.send(f"❌ **오류:** 채널 이름 변경 중 알 수 없는 오류가 발생했습니다.", delete_after=10)
        print(f"[오류] 채널 이름 변경 중 오류 발생: {type(e).__name__}: {e}")


# --- 봇 실행 ---

# 최종 유효성 검사 (실제 토큰과 채널 ID가 플레이스홀더가 아닐 경우에만 실행)
TOKEN_PLACEHOLDER = "YOUR_REGENERATED_BOT_TOKEN_HERE"
if TOKEN == TOKEN_PLACEHOLDER:
    print("\n\n!! 오류: 봇 토큰이 설정되지 않았습니다. !!")
    print("!! 파일 상단의 'TOKEN' 변수에 실제 봇 토큰을 입력했는지 확인하세요. !!\n")
else:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"봇 실행에 실패했습니다: {e}")

        print("토큰이 올바른지, 디스코드 개발자 포털에서 필요한 Intent(특히 Member, Message Content, Voice State Intent)를 활성화했는지 확인해주세요.")
