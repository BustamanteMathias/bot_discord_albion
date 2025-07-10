import discord
import json
import os
from discord.ext import commands
from discord.ui import View, Button
# =======================
# CONFIGURACIÓN EMBEBIDA
# =======================
TOKEN = os.getenv("TOKEN")
PREFIJO = os.getenv("PREFIX")
ROLE_PARTY_LEADER = os.getenv("ROL_CAPITAN")
ROLE_MEMBER = os.getenv("ROL_MIEMBRO")

# ======================
# DECORADORES DE CHECKS
# ======================
def es_party_leader():
    def predicate(ctx):
        if any(role.name == ROLE_PARTY_LEADER for role in ctx.author.roles):
            return True
        raise commands.CheckFailure(f"⛔ No tenés el rol necesario ({ROLE_PARTY_LEADER}) para usar este comando.")
    return commands.check(predicate)

def es_member_o_leader():
    def predicate(ctx):
        nombres_roles = [role.name for role in ctx.author.roles]
        if ROLE_PARTY_LEADER in nombres_roles or ROLE_MEMBER in nombres_roles:
            return True
        raise commands.CheckFailure(f"⛔ Solo miembros o líderes pueden usar este comando.")
    return commands.check(predicate)

# ======================
# CONFIG BOT E INTENTS
# ======================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix=PREFIJO, intents=intents)

SCORES_FILE = "_scores.json"
HISTORIAL_FILE = "_historial_parties.json"
MULTAS_FILE = "_multas.json"
BANS_FILE = "_bans.json"
wb_parties = {}
WB_ROLES = ["maintank", "offtank", "healer", "pajaro", "perma", "maldi", "fuego", "montura", "scout"]
REACTIONS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

# ======================
# FUNCIONES UTILES
# ======================
def cargar_puntos():
    if not os.path.exists(SCORES_FILE):
        return {}
    with open(SCORES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_puntos(data):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def guardar_historial(data):
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            historial = json.load(f)
    else:
        historial = []
    historial.insert(0, data)
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=2)

def cargar_multas():
    if not os.path.exists(MULTAS_FILE):
        return {}
    with open(MULTAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_multas(data):
    with open(MULTAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def cargar_bans():
    if not os.path.exists(BANS_FILE):
        return []
    with open(BANS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_bans(data):
    with open(BANS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

async def generar_campos_embed(embed, guild):
    for i, rol in enumerate(WB_ROLES):
        canal_name = f"b-{rol}"
        canal = discord.utils.get(guild.text_channels, name=canal_name)
        canal_link = f"(https://discord.com/channels/{guild.id}/{canal.id})" if canal else "[N/A]"

        new_title = f"{REACTIONS[i]} {rol.capitalize()}\n{canal_link}"
        embed.add_field(name=new_title, value="—", inline=True)

async def actualizar_embed(msg, party_data, embed):
    puntos = cargar_puntos()
    multas = cargar_multas()
    bans = cargar_bans()

    for i, rol in enumerate(WB_ROLES):
        miembros_texto = []
        for m in sorted(party_data["roles"][rol], key=lambda x: puntos.get(str(x['id']), {}).get('puntos_actuales', 0), reverse=True):
            uid = str(m['id'])
            deuda = multas.get(uid, {}).get("deuda", 0.0)
            tiene_ban = uid in bans

            nombre = m['nombre']
            puntos_actuales = puntos.get(uid, {}).get('puntos_actuales', 0)

            if deuda > 0 or tiene_ban:
                miembros_texto.append(f"```diff\n- {nombre} ({puntos_actuales})```")
            else:
                miembros_texto.append(f"{nombre} ({puntos_actuales})")

        texto = "\n".join(miembros_texto) if miembros_texto else "—"

        canal_name = f"b-{rol}"
        canal = discord.utils.get(msg.guild.text_channels, name=canal_name)
        canal_link = f"https://discord.com/channels/{msg.guild.id}/{canal.id}" if canal else "[N/A]"

        new_title = f"{REACTIONS[i]} {rol.capitalize()}\n{canal_link}"
        embed.set_field_at(i, name=new_title, value=texto, inline=True)

    await msg.edit(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id not in wb_parties:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member.bot:
        return

    party_data = wb_parties[payload.message_id]
    if party_data["cerrada"]:
        return

    puntos = cargar_puntos()
    uid = str(member.id)
    puntos.setdefault(uid, {"puntos_actuales": 0, "puntos_obtenidos": 0, "puntos_usados": 0})

    try:
        idx = REACTIONS.index(str(payload.emoji))
    except ValueError:
        return

    rol_name = WB_ROLES[idx]

    for r in WB_ROLES:
        party_data["roles"][r] = [u for u in party_data["roles"][r] if u["id"] != member.id]

    party_data["roles"][rol_name].append({"id": member.id, "nombre": member.display_name})

    channel = guild.get_channel(payload.channel_id)
    msg = await channel.fetch_message(payload.message_id)
    embed = msg.embeds[0]
    await actualizar_embed(msg, party_data, embed)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.message_id not in wb_parties:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member.bot:
        return

    party_data = wb_parties[payload.message_id]
    if party_data["cerrada"]:
        return

    for r in WB_ROLES:
        party_data["roles"][r] = [u for u in party_data["roles"][r] if u["id"] != member.id]

    channel = guild.get_channel(payload.channel_id)
    msg = await channel.fetch_message(payload.message_id)
    embed = msg.embeds[0]
    await actualizar_embed(msg, party_data, embed)

# ======================
# COMANDOS
# ======================
@bot.command()
@es_party_leader()
async def ban(ctx, member: discord.Member):
    bans = cargar_bans()
    uid = str(member.id)

    if uid in bans:
        return await ctx.send(f"⚠️ {member.display_name} ya está baneado.")

    bans.append(uid)
    guardar_bans(bans)
    await ctx.send(f"🚫 {member.display_name} ha sido baneado.")

@bot.command()
@es_party_leader()
async def unban(ctx, member: discord.Member):
    bans = cargar_bans()
    uid = str(member.id)

    if uid not in bans:
        return await ctx.send(f"⚠️ {member.display_name} no está baneado.")

    bans.remove(uid)
    guardar_bans(bans)
    await ctx.send(f"✅ {member.display_name} ha sido desbaneado.")

@bot.command()
async def bans(ctx):
    bans = cargar_bans()

    if not bans:
        return await ctx.send("✅ No hay usuarios baneados.")

    embed = discord.Embed(title="🚫 Lista de Baneados", color=discord.Color.dark_red())

    for uid in bans:
        member = ctx.guild.get_member(int(uid))
        nombre = member.display_name if member else "Usuario desconocido"
        embed.add_field(name=nombre, value=f"ID: {uid}", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="wbhistorial")
@es_party_leader()
async def wb_historial(ctx):
    if not os.path.exists(HISTORIAL_FILE):
        return await ctx.send("❌ No hay historial disponible.")

    with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
        historial = json.load(f)

    if not historial:
        return await ctx.send("❌ Historial vacío.")

    paginas = [historial[i:i+1] for i in range(0, len(historial), 1)]
    total_paginas = len(paginas)
    index = 0

    def crear_embed(entry, num_pagina):
        hora = entry['hora']
        fecha = entry.get('fecha', 'Sin fecha')
        leader_id = entry.get("leader_id", "?")
        descuento = entry.get("descuento", 0)

        embed = discord.Embed(
            title=f"Party WB - {hora[:2]}:{hora[2:]} UTC | {fecha} {num_pagina}/{total_paginas}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Líder de Party", value=f"<@{leader_id}>", inline=False)
        embed.add_field(name="Puntos descontados", value=str(descuento), inline=False)

        miembros = []
        for rol in WB_ROLES:
            for m in entry["roles"].get(rol, []):
                miembros.append(m)

        if miembros:
            texto = "\n".join([f"{i+1}. <@{m['id']}>" for i, m in enumerate(miembros)])
        else:
            texto = "No hubo miembros."

        embed.add_field(name="Miembros", value=texto, inline=False)
        return embed

    view = View()

    async def actualizar(mensaje):
        await mensaje.edit(embed=crear_embed(paginas[index][0], index + 1), view=view)

    class Anterior(Button):
        def __init__(self):
            super().__init__(label="⬅️ Anterior", style=discord.ButtonStyle.primary)
        async def callback(self, interaction):
            nonlocal index
            if index > 0:
                index -= 1
                await actualizar(interaction.message)
                await interaction.response.defer()

    class Siguiente(Button):
        def __init__(self):
            super().__init__(label="➡️ Siguiente", style=discord.ButtonStyle.primary)
        async def callback(self, interaction):
            nonlocal index
            if index < len(paginas)-1:
                index += 1
                await actualizar(interaction.message)
                await interaction.response.defer()

    view.add_item(Anterior())
    view.add_item(Siguiente())

    await ctx.send(embed=crear_embed(paginas[index][0], index + 1), view=view)

@bot.command()
async def comandos(ctx):
    embed = discord.Embed(title="📜 Lista de Comandos", color=discord.Color.green())

    embed.add_field(name=f"{PREFIJO}score", value="[Miembros] [Líderes] | Ver tus puntos actuales. [Líderes] pueden usar: !score @usuario X para sumar/restar puntos.", inline=False)
    embed.add_field(name=f"{PREFIJO}scores", value="[Miembros] | Ver ranking completo del gremio con paginación.", inline=False)
    embed.add_field(name=f"{PREFIJO}ranking", value="[Miembros] | Ver el top 10 de puntos obtenidos.", inline=False)
    embed.add_field(name=f"{PREFIJO}wb [hora]", value="[Líderes] | Crear party WB. Ejemplo: !wb 1800.", inline=False)
    embed.add_field(name=f"{PREFIJO}wbhistorial", value="[Líderes] | Ver historial de parties anteriores.", inline=False)
    embed.add_field(name=f"{PREFIJO}multa", value="[Miembros] | Ver tu propia deuda actual.", inline=False)
    embed.add_field(name=f"{PREFIJO}multa @usuario <monto>", value="[Líderes] | Sumar/restar deuda a un usuario. Ejemplo: !multa @user 1.5 o !multa @user -3.", inline=False)
    embed.add_field(name=f"{PREFIJO}multas", value="[Líderes] | Ver lista completa de multas.", inline=False)
    embed.add_field(name=f"{PREFIJO}ban @usuario", value="[Líderes] | Banear un usuario.", inline=False)
    embed.add_field(name=f"{PREFIJO}unban @usuario", value="[Líderes] | Desbanear un usuario.", inline=False)
    embed.add_field(name=f"{PREFIJO}bans", value="[Miembros] | Ver lista de usuarios baneados.", inline=False)
    embed.add_field(name=f"{PREFIJO}scorereset", value="[Líderes] | Reinicia todos los puntajes del gremio y deja a todos en 0.", inline=False)
    embed.add_field(name=f"{PREFIJO}prefix <nuevo_prefijo>", value="[Líderes] | Cambiar el prefijo del bot. Ejemplo: !prefix ?", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def multa(ctx, member: discord.Member = None, valor: float = None):
    multas = cargar_multas()

    if member and valor is not None:
        # Check manual: solo líderes pueden modificar
        if not any(role.name == ROLE_PARTY_LEADER for role in ctx.author.roles):
            return await ctx.send(f"⛔ Solo los líderes ({ROLE_PARTY_LEADER}) pueden modificar multas.")
        
        uid = str(member.id)
        data = multas.get(uid, {"deuda": 0.0, "total": 0.0, "pago": 0.0})

        if valor >= 0:
            data["deuda"] += valor
            data["total"] += valor
        else:
            pago_realizado = abs(valor)
            data["deuda"] += valor
            data["pago"] += pago_realizado

            if data["deuda"] < 0:
                data["pago"] += data["deuda"]
                data["deuda"] = 0.0

        multas[uid] = data
        guardar_multas(multas)
        return await ctx.send(f"✅ Multa actualizada para {member.mention}. Deuda: {data['deuda']:.2f}")

    elif not member and valor is None:
        # Consulta personal (disponible para miembros y líderes)
        uid = str(ctx.author.id)
        data = multas.get(uid)

        if not data:
            return await ctx.send("❌ No tenés multas registradas.")

        embed = discord.Embed(title=f"Multas {ctx.author.display_name}", color=discord.Color.red())
        embed.add_field(name="Deuda", value=f"{data['deuda']:.2f}", inline=True)
        embed.add_field(name="Total", value=f"{data['total']:.2f}", inline=True)
        embed.add_field(name="Pago", value=f"{data['pago']:.2f}", inline=True)

        return await ctx.send(embed=embed)

    else:
        await ctx.send("❌ Uso incorrecto. Para sumar/restar: `!multa @usuario X`. Para consultar: `!multa`.")

@bot.command()
@es_party_leader()
async def multas(ctx):
    multas = cargar_multas()

    if not multas:
        return await ctx.send("❌ No hay multas registradas.")

    embed = discord.Embed(title="📄 Lista de Multas", color=discord.Color.blue())

    for uid, data in multas.items():
        member = ctx.guild.get_member(int(uid))
        if member:
            nombre = member.display_name
        else:
            nombre = "Usuario desconocido"

        valor = f"Deuda: {data['deuda']:.2f} | Total: {data['total']:.2f} | Pago: {data['pago']:.2f}"
        embed.add_field(name=nombre, value=valor, inline=False)

    await ctx.send(embed=embed)

@bot.command()
@es_party_leader()
async def wb(ctx, hora_utc: str):
    from datetime import datetime
    fecha_actual = datetime.utcnow().strftime("%d/%m/%Y")

    hora_formateada = f"{hora_utc[:2]}:{hora_utc[2:]}"
    party_data = {
        "leader_id": ctx.author.id,
        "hora": hora_utc,
        "fecha": fecha_actual,
        "roles": {rol: [] for rol in WB_ROLES},
        "cerrada": False,
        "iniciada": False,
        "descuento": 0
    }

    embed = discord.Embed(
        title=f"Party WB - {hora_formateada} UTC | {fecha_actual}",
        description=f"Leader: {ctx.author.mention}\nPuntos a descontar: 0\nEstado: ⏳ Esperando inicio",
        color=discord.Color.dark_red()
    )

    for i, rol in enumerate(WB_ROLES):
        canal_name = f"b-{rol}"
        canal = discord.utils.get(ctx.guild.text_channels, name=canal_name)
        canal_link = f"https://discord.com/channels/{ctx.guild.id}/{canal.id}" if canal else "[N/A]"

        new_title = f"{REACTIONS[i]} {rol.capitalize()}\n{canal_link}"
        embed.add_field(name=new_title, value="—", inline=True)

    class ControlButtons(View):
        def __init__(self):
            super().__init__(timeout=None)
            self.iniciar = self.Iniciar()
            self.add_item(self.iniciar)
            self.add_item(self.Sumar())
            self.add_item(self.Restar())
            self.add_item(self.Finalizar())

        class Iniciar(Button):
            def __init__(self):
                super().__init__(label="✅ Iniciar Party", style=discord.ButtonStyle.success)

            async def callback(self, interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("⛔ Solo el leader puede iniciar la party.", ephemeral=True)
                party_data["iniciada"] = True
                embed.description = f"Leader: {ctx.author.mention}\nPuntos a descontar: {party_data['descuento']}\nEstado: ⚔️ Party en curso"
                self.disabled = True
                await actualizar_embed(interaction.message, party_data, embed)
                await interaction.message.edit(embed=embed, view=self.view)
                await interaction.message.clear_reactions()
                await interaction.response.send_message("⚔️ Party iniciada.", ephemeral=True)

        class Sumar(Button):
            def __init__(self):
                super().__init__(label="➕", style=discord.ButtonStyle.secondary)

            async def callback(self, interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("⛔ Solo el leader puede sumar puntos.", ephemeral=True)
                party_data["descuento"] += 1
                embed.description = f"Leader: {ctx.author.mention}\nPuntos a descontar: {party_data['descuento']}\nEstado: ⚔️ Party en curso" if party_data["iniciada"] else f"Leader: {ctx.author.mention}\nPuntos a descontar: {party_data['descuento']}\nEstado: ⏳ Esperando inicio"
                await actualizar_embed(interaction.message, party_data, embed)
                await interaction.message.edit(embed=embed, view=self.view)
                #await interaction.response.send_message("➕ Descuento actualizado.", ephemeral=True)

        class Restar(Button):
            def __init__(self):
                super().__init__(label="➖", style=discord.ButtonStyle.secondary)

            async def callback(self, interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("⛔ Solo el leader puede restar puntos.", ephemeral=True)
                if party_data["descuento"] > 0:
                    party_data["descuento"] -= 1
                    embed.description = f"Leader: {ctx.author.mention}\nPuntos a descontar: {party_data['descuento']}\nEstado: ⚔️ Party en curso" if party_data["iniciada"] else f"Leader: {ctx.author.mention}\nPuntos a descontar: {party_data['descuento']}\nEstado: ⏳ Esperando inicio"
                    await actualizar_embed(interaction.message, party_data, embed)
                    await interaction.message.edit(embed=embed, view=self.view)
                    #await interaction.response.send_message("➖ Descuento actualizado.", ephemeral=True)
                else:
                    await interaction.response.send_message("⚠️ No puede ser menor a 0.", ephemeral=True)

        class Finalizar(Button):
            def __init__(self):
                super().__init__(label="❌ Finalizar Party", style=discord.ButtonStyle.danger)

            async def callback(self, interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("⛔ Solo el leader puede finalizar la party.", ephemeral=True)
                party_data["cerrada"] = True
                embed.description = f"Leader: {ctx.author.mention}\nPuntos a descontar: {party_data['descuento']}\nEstado: ✅ Party finalizada"
                await actualizar_embed(interaction.message, party_data, embed)
                await interaction.message.edit(embed=embed, view=None)
                puntos = cargar_puntos()
                descontados = []
                for lista in party_data["roles"].values():
                    for miembro in lista:
                        uid = str(miembro["id"])
                        if uid not in puntos:
                            continue
                        puntos[uid]["puntos_actuales"] -= party_data["descuento"]
                        puntos[uid]["puntos_usados"] += party_data["descuento"]
                        descontados.append(f"<@{uid}>")
                guardar_puntos(puntos)
                guardar_historial(party_data)
                await interaction.channel.send(f"✅ Se descontaron {party_data['descuento']} puntos a los miembros: {', '.join(descontados)}")
                await interaction.response.send_message("✅ Party finalizada.", ephemeral=True)

    msg = await ctx.send(embed=embed, view=ControlButtons())
    wb_parties[msg.id] = party_data

    for emoji in REACTIONS:
        await msg.add_reaction(emoji)

    await msg.create_thread(name=f"WB {hora_formateada} - Discusión")

@bot.command()
async def score(ctx, *args):
    puntos = cargar_puntos()
    es_lider = any(role.name == ROLE_PARTY_LEADER for role in ctx.author.roles)
    es_miembro = any(role.name == ROLE_MEMBER for role in ctx.author.roles)

    if not (es_lider or es_miembro):
        return await ctx.send("⛔ No tenés permiso para usar este comando.")

    if len(args) == 0:
        user_id = str(ctx.author.id)
        data = puntos.get(user_id)
        if not data:
            return await ctx.send("❌ No tenés puntos registrados.")
        embed = discord.Embed(title=f"📊 Puntos de {ctx.author.display_name}", color=discord.Color.blue())
        embed.add_field(name="Actuales", value=str(data['puntos_actuales']), inline=True)
        embed.add_field(name="Obtenidos", value=str(data['puntos_obtenidos']), inline=True)
        embed.add_field(name="Usados", value=str(data['puntos_usados']), inline=True)
        return await ctx.send(embed=embed)
    elif es_lider:
        try:
            valor = int(args[-1])
            menciones = ctx.message.mentions
            if not menciones:
                return await ctx.send("❌ Tenés que mencionar al menos un usuario.")
            for user in menciones:
                uid = str(user.id)
                data = puntos.get(uid, {"puntos_actuales": 0, "puntos_obtenidos": 0, "puntos_usados": 0})
                data["puntos_actuales"] += valor
                if valor >= 0:
                    data["puntos_obtenidos"] += valor
                else:
                    data["puntos_usados"] += abs(valor)
                puntos[uid] = data
            guardar_puntos(puntos)
            return await ctx.send(f"✅ Se actualizaron los puntos en {len(menciones)} usuarios.")
        except ValueError:
            return await ctx.send("❌ El último argumento debe ser un número para sumar o restar puntos.")

@bot.command()
async def ranking(ctx):
    puntos = cargar_puntos()
    if not puntos:
        return await ctx.send("❌ No hay datos de puntos todavía.")

    ranking = sorted(puntos.items(), key=lambda item: item[1].get("puntos_obtenidos", 0), reverse=True)
    embed = discord.Embed(title="🏆 Ranking de puntos obtenidos (Top 10)", color=discord.Color.gold())
    embed.add_field(name="POS", value="\n".join([str(i+1) for i in range(min(10, len(ranking)))]), inline=True)
    embed.add_field(name="Miembro", value="\n".join([
        ctx.guild.get_member(int(uid)).display_name if ctx.guild.get_member(int(uid)) else "-"
        for uid, _ in ranking[:10]
    ]), inline=True)
    embed.add_field(name="Obtenidos", value="\n".join([
        str(data["puntos_obtenidos"]) for _, data in ranking[:10]
    ]), inline=True)
    await ctx.send(embed=embed)

@bot.command()
@es_party_leader()
async def scorereset(ctx):
    puntos = {}
    for member in ctx.guild.members:
        if member.bot:
            continue
        uid = str(member.id)
        puntos[uid] = {
            "puntos_actuales": 0,
            "puntos_obtenidos": 0,
            "puntos_usados": 0
        }

    guardar_puntos(puntos)
    await ctx.send("✅ ¡Todos los puntos han sido reseteados y todos los miembros inicializados en 0!")

@bot.command()
async def scores(ctx):
    puntos = cargar_puntos()
    if not puntos:
        return await ctx.send("❌ No hay puntos registrados todavía.")

    # Ordenar por puntos actuales, de mayor a menor
    ranking = sorted(puntos.items(), key=lambda item: item[1].get("puntos_actuales", 0), reverse=True)
    paginas = [ranking[i:i + 10] for i in range(0, len(ranking), 10)]
    total_paginas = len(paginas)
    index = 0

    def crear_embed(pagina, num_pagina):
        embed = discord.Embed(title="Score de Gremio", color=discord.Color.purple())
        descripcion = ""
        for idx, (uid, data) in enumerate(pagina, start=1 + num_pagina * 10 - 10):
            member = ctx.guild.get_member(int(uid))
            nombre = member.display_name if member else "Usuario desconocido"
            puntos_actuales = data.get("puntos_actuales", 0)
            descripcion += f"**{idx}. {nombre}** — {puntos_actuales} puntos\n"

        embed.description = descripcion
        embed.set_footer(text=f"Página {num_pagina}/{total_paginas}")
        return embed

    view = View()

    async def actualizar(mensaje):
        embed = crear_embed(paginas[index], index + 1)
        await mensaje.edit(embed=embed, view=view)

    class Anterior(Button):
        def __init__(self):
            super().__init__(label="⬅️ Anterior", style=discord.ButtonStyle.primary)
        async def callback(self, interaction):
            nonlocal index
            if index > 0:
                index -= 1
                await actualizar(interaction.message)
                await interaction.response.defer()

    class Siguiente(Button):
        def __init__(self):
            super().__init__(label="➡️ Siguiente", style=discord.ButtonStyle.primary)
        async def callback(self, interaction):
            nonlocal index
            if index < len(paginas) - 1:
                index += 1
                await actualizar(interaction.message)
                await interaction.response.defer()

    view.add_item(Anterior())
    view.add_item(Siguiente())

    mensaje = await ctx.send(embed=crear_embed(paginas[index], index + 1), view=view)

@bot.command()
@es_party_leader()
async def prefix(ctx, nuevo_prefijo: str = None):
    global PREFIJO

    if not nuevo_prefijo:
        return await ctx.send("❌ Tenés que especificar un nuevo prefijo. Ejemplo: `!prefix ?`")

    bot.command_prefix = nuevo_prefijo
    PREFIJO = nuevo_prefijo

    await ctx.send(f"✅ Prefijo actualizado correctamente a `{nuevo_prefijo}`")

# ======================
# EJECUTAR BOT
# ======================
bot.run(TOKEN)
