# bot.py
import discord
from discord import app_commands
from discord.ext import commands
import json, asyncio, os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

BALANCE_FILE = "balances.json"
ADMIN_IDS = {826753238392111106}  # ide teheted a saját ID-d is

ROLE_DAILY_PAYOUT = {
    1432248746011394128: 1000,
    1432248893046784050: 2000,
    1432249242419728439: 3500,
    1432249330714021888: 5000,
}

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

data_lock = asyncio.Lock()
data = {"economy": {}, "shulk": {}}


# ---- Segédfüggvények ----
def save_to_file():
    with open(BALANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


async def load_from_file():
    global data
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        save_to_file()


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except:
        return None


@bot.event
async def on_ready():
    await load_from_file()
    await bot.tree.sync()
    print(f"✅ Bejelentkezve: {bot.user}")


# ---- Egyenlegkezelés ----
def get_econ(uid):
    return data["economy"].get(str(uid), {"balance": 0, "last_claim": None})


def get_shulk(uid):
    return data["shulk"].get(str(uid), 0)


async def update_econ(uid, diff=0, last_claim=None):
    async with data_lock:
        u = get_econ(uid)
        u["balance"] += diff
        if last_claim:
            u["last_claim"] = last_claim
        data["economy"][str(uid)] = u
        save_to_file()


async def update_shulk(uid, diff=0):
    async with data_lock:
        bal = get_shulk(uid)
        bal += diff
        data["shulk"][str(uid)] = max(0, bal)
        save_to_file()


# ---- Parancsok ----
@bot.tree.command(name="enapi", description="Napi juttatás a rangod alapján.")
async def enapi(interaction: discord.Interaction):
    await interaction.response.defer()
    member = interaction.user
    role_ids = {r.id for r in member.roles}
    payout = max((ROLE_DAILY_PAYOUT[r] for r in role_ids if r in ROLE_DAILY_PAYOUT), default=None)

    if payout is None:
        await interaction.followup.send("🚫 Nincs megfelelő rangod a napi jutalomhoz.")
        return

    entry = get_econ(member.id)
    last = parse_iso(entry.get("last_claim"))
    now = datetime.now(timezone.utc)

    if last and now - last < timedelta(days=1):
        rem = timedelta(days=1) - (now - last)
        hrs = int(rem.total_seconds() // 3600)
        mins = int(rem.total_seconds() % 3600 // 60)
        await interaction.followup.send(f"🕒 Már igényelted ma. Várj még {hrs} óra {mins} percet.")
        return

    await update_econ(member.id, diff=payout, last_claim=iso_now())
    await interaction.followup.send(f"💸 Kaptál **{payout}$** napi juttatást!")


@bot.tree.command(name="ebal", description="Economy egyenleg megtekintése.")
async def ebal(interaction: discord.Interaction):
    bal = get_econ(interaction.user.id)["balance"]
    await interaction.response.send_message(f"💰 Ennyi beváltható economy pénzed van: **{bal}$**")


@bot.tree.command(name="sbal", description="ShulkCredit egyenleg megtekintése.")
async def sbal(interaction: discord.Interaction):
    bal = get_shulk(interaction.user.id)
    await interaction.response.send_message(f"🟣 ShulkCredit egyenleged: **{bal} SC**")


# ---- Admin Only parancsok ----
def admin_check(user):
    return user.id in ADMIN_IDS or user.guild_permissions.administrator


@bot.tree.command(name="eadd", description="Admin: hozzáad economy pénzt egy felhasználónak.")
async def eadd(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not admin_check(interaction.user):
        await interaction.response.send_message("🚫 Nincs jogod ehhez.", ephemeral=True)
        return
    await update_econ(user.id, diff=amount)
    await interaction.response.send_message(f"✅ {user.mention} kapott **{amount}$**-t.")


@bot.tree.command(name="eremove", description="Admin: levon economy pénzt egy felhasználótól.")
async def eremove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not admin_check(interaction.user):
        await interaction.response.send_message("🚫 Nincs jogod ehhez.", ephemeral=True)
        return
    await update_econ(user.id, diff=-abs(amount))
    await interaction.response.send_message(f"❌ {user.mention}-tól levontál **{amount}$**-t.")


@bot.tree.command(name="sadd", description="Admin: hozzáad ShulkCreditet egy felhasználónak.")
async def sadd(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not admin_check(interaction.user):
        await interaction.response.send_message("🚫 Nincs jogod ehhez.", ephemeral=True)
        return
    await update_shulk(user.id, diff=amount)
    await interaction.response.send_message(f"🟣 {user.mention} kapott **{amount} ShulkCreditet**.")


@bot.tree.command(name="sremove", description="Admin: levon ShulkCreditet egy felhasználótól.")
async def sremove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not admin_check(interaction.user):
        await interaction.response.send_message("🚫 Nincs jogod ehhez.", ephemeral=True)
        return
    await update_shulk(user.id, diff=-abs(amount))
    await interaction.response.send_message(f"❌ {user.mention}-tól levontál **{amount} ShulkCreditet**.")


bot.run(TOKEN)
