import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import numpy as np
import random
import json
import aiohttp
import html

# --- Bot Setup ---
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Game Storage ---
active_connect_four_games = {}
active_hangman_games = {}
active_word_ladder_games = {}
active_tictactoe_games = {}
active_anagram_games = {}
active_guess_the_number_games = {}


# --- Word Loading Logic ---
WL_VALID_WORDS = set()
WL_PAIRS = []
HM_EASY_WORDS, HM_MEDIUM_WORDS, HM_HARD_WORDS = [], [], []

try:
    with open('words.json', 'r') as f:
        data = json.load(f)
        ladder_words = [word.upper() for word in data.get('ladder_words', []) if len(word) == 4]
        WL_VALID_WORDS = set(ladder_words)
        if len(ladder_words) > 1:
            for _ in range(20):
                WL_PAIRS.append(tuple(random.sample(ladder_words, 2)))

        hangman_words = data.get('hangman_words', [])
        for word in hangman_words:
            l = len(word)
            if l <= 4: HM_EASY_WORDS.append(word.upper())
            elif l <= 6: HM_MEDIUM_WORDS.append(word.upper())
            else: HM_HARD_WORDS.append(word.upper())
        print("Successfully loaded words from words.json")
except FileNotFoundError:
    print("ERROR: words.json not found.")
except (json.JSONDecodeError, KeyError):
    print("ERROR: words.json is not formatted correctly.")


# --- Game Logic (Grouped by Game) ---

# --- Word Ladder Logic ---
def wl_get_word_pair():
    return random.choice(WL_PAIRS) if WL_PAIRS else ("WORD", "GAME")
def wl_is_valid_move(current, next_w, difficulty="hard"):
    if next_w.upper() not in WL_VALID_WORDS or len(current) != len(next_w): return False
    diff = sum(1 for c1, c2 in zip(current, next_w) if c1 != c2)
    return diff == 1 if difficulty == "hard" else 1 <= diff <= 2
def wl_format_ladder(ladder): return " → ".join(ladder) if ladder else "No words yet."

# --- Connect Four Logic ---
C4_ROWS, C4_COLS, C4_EMPTY, C4_P1, C4_P2 = 6, 7, "⚪", "🔴", "🟡"
def c4_create_board(): return np.full((C4_ROWS, C4_COLS), C4_EMPTY)
def c4_drop_piece(b, r, c, p): b[r][c] = p
def c4_is_valid_location(b, c): return b[0][c] == C4_EMPTY
def c4_get_next_open_row(b, c):
    for r in range(C4_ROWS - 1, -1, -1):
        if b[r][c] == C4_EMPTY: return r
    return None
def c4_check_win(b, p):
    for c in range(C4_COLS - 3):
        for r in range(C4_ROWS):
            if all(b[r][c+i] == p for i in range(4)): return True
    for c in range(C4_COLS):
        for r in range(C4_ROWS - 3):
            if all(b[r+i][c] == p for i in range(4)): return True
    for c in range(C4_COLS - 3):
        for r in range(C4_ROWS - 3):
            if all(b[r+i][c+i] == p for i in range(4)): return True
    for c in range(C4_COLS - 3):
        for r in range(3, C4_ROWS):
            if all(b[r-i][c+i] == p for i in range(4)): return True
    return False
def c4_format_board(b):
    h = "".join([f"{i+1}\u20e3" for i in range(C4_COLS)]) + "\n"
    return h + "\n".join(["".join(r) for r in b])

# --- Hangman Logic ---
HANGMAN_PICS = ['```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========\n```', '```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========\n```', '```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========\n```', '```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========\n```', '```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========\n```', '```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========\n```', '```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========\n```']
def hm_get_random_word(difficulty="medium"):
    if difficulty == "easy" and HM_EASY_WORDS: return random.choice(HM_EASY_WORDS)
    if difficulty == "hard" and HM_HARD_WORDS: return random.choice(HM_HARD_WORDS)
    return random.choice(HM_MEDIUM_WORDS) if HM_MEDIUM_WORDS else "PUZZLE"
def hm_format_display(w, g): return "".join([f" {l} " if l in g else " __ " for l in w])

# --- Tic-Tac-Toe Logic ---
TTT_EMPTY, TTT_P1, TTT_P2 = "➖", "❌", "⭕"
def ttt_check_win(b, p):
    wins = [[(0,0),(0,1),(0,2)],[(1,0),(1,1),(1,2)],[(2,0),(2,1),(2,2)],[(0,0),(1,0),(2,0)],[(0,1),(1,1),(2,1)],[(0,2),(1,2),(2,2)],[(0,0),(1,1),(2,2)],[(0,2),(1,1),(2,0)]]
    for w in wins:
        if all(b[r][c] == p for r,c in w): return True
    return False

# --- Anagrams Logic ---
def get_anagram_word(d="medium"): return hm_get_random_word(d)
def scramble_word(w):
    s = list(w); random.shuffle(s); scrambled = "".join(s)
    return scramble_word(w) if scrambled == w else scrambled


# --- Guess the Number Logic ---
def gtn_generate_number(): return random.randint(1, 100)

# --- Discord UI Views ---
class C4GameView(discord.ui.View):
    def __init__(self, gs):
        super().__init__(timeout=300); self.game_state = gs
        for i in range(C4_COLS): self.add_item(C4ColumnButton(str(i+1), i))
    async def interaction_check(self, i):
        if i.user.id != self.game_state["players"][self.game_state["turn_index"]].id:
            await i.response.send_message("It's not your turn!", ephemeral=True); return False
        return True
    async def handle_win(self, i, w):
        for item in self.children: item.disabled = True
        e = i.message.embeds[0]; e.description = f"**🎉 {w.mention} wins! 🎉**\n\n{c4_format_board(self.game_state['board'])}"; e.color = discord.Color.green()
        await i.response.edit_message(embed=e, view=self); del active_connect_four_games[i.message.id]
    async def handle_draw(self, i):
        for item in self.children: item.disabled = True
        e = i.message.embeds[0]; e.description = f"**🤝 It's a draw! 🤝**\n\n{c4_format_board(self.game_state['board'])}"; e.color = discord.Color.gold()
        await i.response.edit_message(embed=e, view=self); del active_connect_four_games[i.message.id]
class C4ColumnButton(discord.ui.Button):
    def __init__(self, l, c):
        super().__init__(style=discord.ButtonStyle.secondary, label=l); self.column = c
    async def callback(self, i):
        gs, b = self.view.game_state, self.view.game_state["board"]
        if not c4_is_valid_location(b, self.column): await i.response.send_message("This column is full!", ephemeral=True); return
        r, p = c4_get_next_open_row(b, self.column), gs["pieces"][gs["turn_index"]]
        c4_drop_piece(b, r, self.column, p)
        if c4_check_win(b, p): await self.view.handle_win(i, i.user); return
        if C4_EMPTY not in b: await self.view.handle_draw(i); return
        gs["turn_index"] = 1 - gs["turn_index"]
        e, np = i.message.embeds[0], gs["players"][gs["turn_index"]]
        e.description = f"{c4_format_board(b)}\n\nIt's **{np.mention}'s** turn ({gs['pieces'][gs['turn_index']]})"
        await i.response.edit_message(embed=e, view=self.view)
class C4ChallengeView(discord.ui.View):
    def __init__(self, ch, op):
        super().__init__(timeout=60); self.challenger, self.opponent = ch, op
    async def interaction_check(self, i):
        if i.user.id != self.opponent.id: await i.response.send_message("This challenge is not for you.", ephemeral=True); return False
        return True
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, i, b):
        gs = {"board": c4_create_board(), "players": [self.challenger, self.opponent], "pieces": [C4_P1, C4_P2], "turn_index": 0}
        e = discord.Embed(title=f"Connect Four: {self.challenger.display_name} vs. {self.opponent.display_name}", description=f"{c4_format_board(gs['board'])}\n\nIt's **{self.challenger.mention}'s** turn ({C4_P1})", color=discord.Color.blue())
        await i.response.edit_message(content="Challenge accepted!", embed=e, view=C4GameView(gs))
        msg = await i.original_response(); active_connect_four_games[msg.id] = gs; self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, i, b): await i.response.edit_message(content=f"{self.opponent.mention} declined.", view=None); self.stop()
class HangmanView(discord.ui.View):
    def __init__(self, gs):
        super().__init__(timeout=300); self.game_state = gs
        for i, l in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            if i // 5 >= 5: break
            self.add_item(HangmanLetterButton(l, i // 5))
    async def interaction_check(self, i):
        if i.user.id != self.game_state["player"].id: await i.response.send_message("This is not your game!", ephemeral=True); return False
        return True
    async def update_game(self, i):
        gs = self.game_state; wd = hm_format_display(gs["word"], gs["guessed"]); dr = HANGMAN_PICS[gs["wrong_guesses"]]
        e = i.message.embeds[0]; e.description = f"{dr}\n\nThe word has **{len(gs['word'])}** letters.\n\n**Word:**{wd}\n\n**Guessed:** {' '.join(sorted(list(gs['guessed'])))}"
        if " __ " not in wd:
            e.color, e.title = discord.Color.green(), "🎉 You Win! 🎉"
            for item in self.children: item.disabled = True
            del active_hangman_games[i.message.id]
        elif gs["wrong_guesses"] >= len(HANGMAN_PICS) - 1:
            e.color, e.title = discord.Color.red(), "💀 You Lost! 💀"; e.description = f"{dr}\n\nThe word was: **{gs['word']}**"
            for item in self.children: item.disabled = True
            del active_hangman_games[i.message.id]
        await i.response.edit_message(embed=e, view=self)
class HangmanLetterButton(discord.ui.Button):
    def __init__(self, l, r):
        super().__init__(style=discord.ButtonStyle.secondary, label=l, row=r); self.letter = l
    async def callback(self, i):
        gs = self.view.game_state; self.disabled = True; gs["guessed"].add(self.letter)
        if self.letter not in gs["word"]: gs["wrong_guesses"] += 1
        await self.view.update_game(i)
class WordLadderView(discord.ui.View):
    def __init__(self, gs):
        super().__init__(timeout=300); self.game_state = gs
    async def interaction_check(self, i):
        if i.user.id not in [p.id for p in self.game_state["players"]]: await i.response.send_message("This is not your game!", ephemeral=True); return False
        return True
    @discord.ui.button(label="Make a Move", style=discord.ButtonStyle.primary)
    async def make_move_button(self, i, b): await i.response.send_modal(WordLadderInputModal(self.game_state))
class WordLadderInputModal(discord.ui.Modal, title="Submit Your Next Word"):
    def __init__(self, gs):
        super().__init__(); self.game_state = gs
        self.next_word = discord.ui.TextInput(label="Your Word", placeholder="Enter the next word...", min_length=len(gs["start_word"]), max_length=len(gs["start_word"]))
        self.add_item(self.next_word)
    async def on_submit(self, i):
        pi = 0 if len(self.game_state["players"]) == 1 or i.user.id == self.game_state["players"][0].id else 1
        pl, cw, nwi = self.game_state["ladders"][pi], self.game_state["ladders"][pi][-1], self.next_word.value.upper()
        if not wl_is_valid_move(cw, nwi, self.game_state["difficulty"]): await i.response.send_message(f"'{nwi}' is not a valid move from '{cw}'.", ephemeral=True); return
        pl.append(nwi)
        e = i.message.embeds[0]
        if len(self.game_state["players"]) == 1:
            e.description = f"**Goal:** `{self.game_state['start_word']}` → `{self.game_state['end_word']}`\n\n**Your Ladder ({len(pl) - 1} points):**\n{wl_format_ladder(pl)}"
        else:
            p1, p2 = self.game_state["players"][0], self.game_state["players"][1]
            e.description = f"**Goal:** `{self.game_state['start_word']}` → `{self.game_state['end_word']}`\n\n**{p1.display_name}'s Ladder ({len(self.game_state['ladders'][0]) - 1} points):**\n{wl_format_ladder(self.game_state['ladders'][0])}\n\n**{p2.display_name}'s Ladder ({len(self.game_state['ladders'][1]) - 1} points):**\n{wl_format_ladder(self.game_state['ladders'][1])}"
        if nwi == self.game_state["end_word"]:
            e.title = f"🎉 {i.user.display_name} Wins! 🎉"; e.color = discord.Color.green()
            await i.response.edit_message(embed=e, view=None); del active_word_ladder_games[i.message.id]
        else: await i.response.edit_message(embed=e)
class WLChallengeView(discord.ui.View):
    def __init__(self, ch, op, d):
        super().__init__(timeout=60); self.challenger, self.opponent, self.difficulty = ch, op, d
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, i, b):
        s, e = wl_get_word_pair()
        gs = {"players": [self.challenger, self.opponent], "start_word": s, "end_word": e, "ladders": [[s], [s]], "difficulty": self.difficulty}
        p1n, p2n = self.challenger.display_name, self.opponent.display_name
        em = discord.Embed(title=f"Word Ladder: {p1n} vs. {p2n}", color=discord.Color.blue(), description=f"**Goal:** `{s}` → `{e}`\n\n**{p1n}'s Ladder (0 points):**\n{wl_format_ladder([s])}\n\n**{p2n}'s Ladder (0 points):**\n{wl_format_ladder([s])}")
        await i.response.edit_message(content="Challenge accepted!", embed=em, view=WordLadderView(gs))
        msg = await i.original_response(); active_word_ladder_games[msg.id] = gs; self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, i, b): await i.response.edit_message(content=f"{self.opponent.mention} declined.", view=None); self.stop()
class TTTGameView(discord.ui.View):
    def __init__(self, gs):
        super().__init__(timeout=300); self.game_state = gs
        for r in range(3):
            for c in range(3): self.add_item(TTTSquareButton(r, c))
    async def interaction_check(self, i):
        if i.user.id != self.game_state["players"][self.game_state["turn_index"]].id: await i.response.send_message("It's not your turn!", ephemeral=True); return False
        return True
    async def handle_win(self, i, w):
        for item in self.children: item.disabled = True
        e = i.message.embeds[0]; e.description = f"**🎉 {w.mention} wins! 🎉**"; e.color = discord.Color.green()
        await i.response.edit_message(embed=e, view=self); del active_tictactoe_games[i.message.id]
    async def handle_draw(self, i):
        for item in self.children: item.disabled = True
        e = i.message.embeds[0]; e.description = "**🤝 It's a draw! 🤝**"; e.color = discord.Color.gold()
        await i.response.edit_message(embed=e, view=self); del active_tictactoe_games[i.message.id]
class TTTSquareButton(discord.ui.Button):
    def __init__(self, r, c):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=r); self.row, self.col = r, c
    async def callback(self, i):
        gs = self.view.game_state; pp = gs["pieces"][gs["turn_index"]]
        gs["board"][self.row][self.col] = pp; self.label = pp; self.style = discord.ButtonStyle.success if pp == TTT_P1 else discord.ButtonStyle.danger; self.disabled = True
        if ttt_check_win(gs["board"], pp): await self.view.handle_win(i, i.user); return
        if all(cell != TTT_EMPTY for row in gs["board"] for cell in row): await self.view.handle_draw(i); return
        gs["turn_index"] = 1 - gs["turn_index"]
        e, np = i.message.embeds[0], gs["players"][gs["turn_index"]]
        e.description = f"It's **{np.mention}'s** turn ({gs['pieces'][gs['turn_index']]})"
        await i.response.edit_message(embed=e, view=self.view)
class TTTChallengeView(discord.ui.View):
    def __init__(self, ch, op):
        super().__init__(timeout=60); self.challenger, self.opponent = ch, op
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, i, b):
        gs = {"board": [[TTT_EMPTY for _ in range(3)] for _ in range(3)], "players": [self.challenger, self.opponent], "pieces": [TTT_P1, TTT_P2], "turn_index": 0}
        e = discord.Embed(title=f"Tic-Tac-Toe: {self.challenger.display_name} vs {self.opponent.display_name}", description=f"It's **{self.challenger.mention}'s** turn ({TTT_P1})", color=discord.Color.blue())
        await i.response.edit_message(content="Challenge accepted!", embed=e, view=TTTGameView(gs))
        msg = await i.original_response(); active_tictactoe_games[msg.id] = gs; self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, i, b): await i.response.edit_message(content=f"{self.opponent.mention} declined.", view=None); self.stop()
class AnagramView(discord.ui.View):
    def __init__(self, gs):
        super().__init__(timeout=120); self.game_state = gs
    @discord.ui.button(label="Guess the Word", style=discord.ButtonStyle.primary)
    async def guess_button(self, i, b): await i.response.send_modal(AnagramInputModal(self.game_state, self))
class AnagramInputModal(discord.ui.Modal, title="Unscramble the Word"):
    def __init__(self, gs, pv):
        super().__init__(); self.game_state, self.parent_view = gs, pv
        self.guess_input = discord.ui.TextInput(label="Your Guess", placeholder="Type the unscrambled word here...")
        self.add_item(self.guess_input)
    async def on_submit(self, i):
        guess = self.guess_input.value.upper(); cw = self.game_state["word"]
        if guess == cw:
            e = i.message.embeds[0]; e.title = f"🎉 {i.user.display_name} Solved It! 🎉"
            e.description = f"The scrambled word was `{self.game_state['scrambled']}`.\n\nThe correct word was **{cw}**!"
            e.color = discord.Color.green()
            for item in self.parent_view.children: item.disabled = True
            await i.response.edit_message(embed=e, view=self.parent_view); del active_anagram_games[i.message.id]
        else: await i.response.send_message(f"Sorry, '{guess}' is not the correct word. Try again!", ephemeral=True)
class GuessTheNumberView(discord.ui.View):
    def __init__(self, gs):
        super().__init__(timeout=180); self.game_state = gs
    @discord.ui.button(label="Make a Guess", style=discord.ButtonStyle.primary)
    async def make_guess_button(self, i, b): await i.response.send_modal(GuessTheNumberInputModal(self.game_state))
class GuessTheNumberInputModal(discord.ui.Modal, title="Guess The Number"):
    def __init__(self, gs):
        super().__init__(); self.game_state = gs
        self.guess_input = discord.ui.TextInput(label="Your Guess (1-100)", placeholder="Enter a number...")
        self.add_item(self.guess_input)
    async def on_submit(self, i):
        if not self.guess_input.value.isdigit(): await i.response.send_message("That's not a valid number!", ephemeral=True); return
        guess = int(self.guess_input.value); gs = self.game_state; gs["guesses"] += 1; e = i.message.embeds[0]
        if guess == gs["number"]:
            e.title = f"🎉 You Guessed It! 🎉"; e.color = discord.Color.green(); e.description = f"You guessed the number **{gs['number']}** in {gs['guesses']} guesses!"
            await i.response.edit_message(embed=e, view=None); del active_guess_the_number_games[i.message.id]
        else:
            hint = "Higher ⬆️" if guess < gs["number"] else "Lower ⬇️"
            e.description = f"Your last guess was `{guess}`. The number is **{hint}**"
            await i.response.edit_message(embed=e)

# --- Bot Commands ---
@bot.event
async def on_ready(): print(f'{bot.user} has connected to Discord!'); await bot.tree.sync()

@bot.tree.command(name="connectfour", description="Challenge a player to Connect Four.")
async def connectfour(i, o: discord.Member):
    if o.bot or o.id == i.user.id: return await i.response.send_message("Invalid opponent.", ephemeral=True)
    await i.response.send_message(f"**Connect Four Challenge!**\n\n{i.user.mention} has challenged {o.mention}.", view=C4ChallengeView(i.user, o))

@bot.tree.command(name="hangman", description="Start a game of Hangman.")
@app_commands.describe(difficulty="How long should the word be?")
@app_commands.choices(difficulty=[app_commands.Choice(name="Easy (3-4 letters)", value="easy"), app_commands.Choice(name="Medium (5-6 letters)", value="medium"), app_commands.Choice(name="Hard (7+ letters)", value="hard")])
async def hangman(interaction: discord.Interaction, difficulty: str = "medium"):
    word = hm_get_random_word(difficulty)
    gs = {"word": word, "guessed": set(), "wrong_guesses": 0, "player": interaction.user}
    e = discord.Embed(title=f"Hangman ({difficulty.title()})", description=f"{HANGMAN_PICS[0]}\n\nThe word has **{len(word)}** letters.\n\n**Word:**{hm_format_display(word, set())}\n\n**Guessed:** (None yet)", color=discord.Color.blue())
    await interaction.response.send_message(embed=e, view=HangmanView(gs))
    msg = await interaction.original_response(); active_hangman_games[msg.id] = gs

@bot.tree.command(name="wordladder", description="Start a game of Word Ladder.")
@app_commands.describe(difficulty="Set the game difficulty.", opponent="The user you want to race (optional).")
@app_commands.choices(difficulty=[app_commands.Choice(name="Easy (1 or 2 letter changes)", value="easy"), app_commands.Choice(name="Hard (1 letter change only)", value="hard")])
async def wordladder(interaction: discord.Interaction, difficulty: str, opponent: discord.Member = None):
    if opponent:
        if opponent.bot or opponent.id == interaction.user.id: return await interaction.response.send_message("Invalid opponent.", ephemeral=True)
        await interaction.response.send_message(f"**Word Ladder Challenge!**\n\n{interaction.user.mention} has challenged {opponent.mention} to a race.", view=WLChallengeView(interaction.user, opponent, difficulty))
    else:
        s, e = wl_get_word_pair(); gs = {"players": [interaction.user], "start_word": s, "end_word": e, "ladders": [[s]], "difficulty": difficulty}
        em = discord.Embed(title=f"Word Ladder ({difficulty.title()})", color=discord.Color.blue(), description=f"**Goal:** `{s}` → `{e}`\n\n**Your Ladder (0 points):**\n{wl_format_ladder([s])}")
        await interaction.response.send_message(embed=em, view=WordLadderView(gs))
        msg = await interaction.original_response(); active_word_ladder_games[msg.id] = gs

@bot.tree.command(name="tictactoe", description="Challenge a player to Tic-Tac-Toe.")
async def tictactoe(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.bot or opponent.id == interaction.user.id: return await interaction.response.send_message("Invalid opponent.", ephemeral=True)
    await interaction.response.send_message(f"**Tic-Tac-Toe Challenge!**\n\n{interaction.user.mention} has challenged {opponent.mention}.", view=TTTChallengeView(interaction.user, opponent))

@bot.tree.command(name="anagram", description="Starts a word scramble game.")
@app_commands.describe(difficulty="How long should the word be?")
@app_commands.choices(difficulty=[app_commands.Choice(name="Easy (3-4 letters)", value="easy"), app_commands.Choice(name="Medium (5-6 letters)", value="medium"), app_commands.Choice(name="Hard (7+ letters)", value="hard")])
async def anagram(interaction: discord.Interaction, difficulty: str = "medium"):
    word = get_anagram_word(difficulty)
    scrambled = scramble_word(word)
    gs = {"word": word, "scrambled": scrambled}
    e = discord.Embed(title=" unscramble the word!", description=f"The first person to unscramble this word wins:\n\n# `{scrambled}`", color=discord.Color.blurple())
    e.set_footer(text=f"Difficulty: {difficulty.title()}")
    await interaction.response.send_message(embed=e, view=AnagramView(gs))
    msg = await interaction.original_response(); active_anagram_games[msg.id] = gs


@bot.tree.command(name="guessthenumber", description="Start a game of Guess the Number.")
async def guessthenumber(i):
    gs = {"number": gtn_generate_number(), "guesses": 0, "player": i.user}
    e = discord.Embed(title="Guess the Number (1-100)", description="I'm thinking of a number between 1 and 100. What's your first guess?", color=discord.Color.teal())
    await i.response.send_message(embed=e, view=GuessTheNumberView(gs))
    msg = await i.original_response(); active_guess_the_number_games[msg.id] = gs

@bot.tree.command(name="help", description="Shows the rules for the games.")
async def help(i):
    e = discord.Embed(title="Puzzles Bot Help", description="Here's how to play the available games:", color=discord.Color.purple())
    e.add_field(name="🔴 Connect Four 🟡", value="**Objective:** Be the first to get four discs in a row.\n**How to Play:** Use `/connectfour @user` to challenge someone.", inline=False)
    e.add_field(name="💀 Hangman 💀", value="**Objective:** Guess the secret word before the hangman is drawn.\n**How to Play:** Use `/hangman` and choose a difficulty to start a solo game.", inline=False)
    e.add_field(name="🪜 Word Ladder 🪜", value="**Objective:** Turn the start word into the end word by changing letters.\n**How to Play:** Use `/wordladder` to play solo or add an `@user` to race.", inline=False)
    e.add_field(name="⚔️ Tic-Tac-Toe ⚔️", value="**Objective:** Be the first to get three of your marks in a row.\n**How to Play:** Use `/tictactoe @user` to challenge someone.", inline=False)
    e.add_field(name=" unscramble the word! Anagrams ", value="**Objective:** Be the first to unscramble the jumbled word.\n**How to Play:** Use `/anagram` and choose a difficulty to start a game for the channel.", inline=False)
    e.add_field(name="🔢 Guess the Number 🔢", value="**Objective:** Guess the secret number between 1 and 100.\n**How to Play:** Use `/guessthenumber` to start. The bot will tell you if your guess is higher or lower.", inline=False)
    await i.response.send_message(embed=e, ephemeral=True)

# --- Run the Bot ---
if __name__ == '__main__':
    if TOKEN: bot.run(TOKEN)
    else: print("ERROR: DISCORD_BOT_TOKEN not found in .env file.")
