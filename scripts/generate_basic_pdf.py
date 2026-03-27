"""
generate_basic_pdf.py
=====================
Generates basic.pdf -- a plain-English guide to the HyperAgents project
aimed at non-technical readers.

Usage:
    python scripts/generate_basic_pdf.py
"""
from __future__ import annotations
from pathlib import Path
from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "basic.pdf"

# Windows system fonts (Unicode-safe)
FONT_DIR = Path("C:/Windows/Fonts")
FONT_REG  = str(FONT_DIR / "arial.ttf")
FONT_BOLD = str(FONT_DIR / "arialbd.ttf")
FONT_ITA  = str(FONT_DIR / "ariali.ttf")

# Colour palette (R, G, B)
BROWN    = (184,  88,  47)
TEAL     = ( 26, 125, 121)
DARK     = ( 40,  30,  18)
MUTED    = (110,  90,  65)
CREAM    = (255, 252, 246)
LIGHT_BG = (245, 238, 228)
LINE     = (210, 195, 175)


class GuideDoc(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.add_font("Arial",  "",  FONT_REG)
        self.add_font("Arial",  "B", FONT_BOLD)
        self.add_font("Arial",  "I", FONT_ITA)
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(22, 20, 22)

    # ------------------------------------------------------------------
    def header(self):
        if self.page == 1:
            return
        self.set_font("Arial", "B", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, "HyperAgents  |  Plain-English Guide", align="L")
        self.cell(0, 8, f"Page {self.page}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(22, self.get_y(), 190, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, "github.com/AISmithy/hyperagents", align="C")

    # ------------------------------------------------------------------
    def _hrule(self):
        self.set_draw_color(*BROWN)
        self.set_line_width(0.7)
        self.line(22, self.get_y(), 190, self.get_y())
        self.ln(4)

    def h1(self, text: str):
        self.ln(5)
        self.set_font("Arial", "B", 16)
        self.set_text_color(*BROWN)
        self.multi_cell(0, 8, text)
        self._hrule()

    def h2(self, text: str):
        self.ln(3)
        self.set_font("Arial", "B", 12)
        self.set_text_color(*TEAL)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def body(self, text: str):
        self.set_font("Arial", "", 11)
        self.set_text_color(*DARK)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def bullet(self, items: list[str]):
        self.set_font("Arial", "", 11)
        self.set_text_color(*DARK)
        indent = 6
        for item in items:
            self.set_x(self.l_margin)
            self.cell(indent, 6, "-", new_x="RIGHT", new_y="TOP")
            self.multi_cell(self.epw - indent, 6, item, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def numbered(self, items: list[str]):
        self.set_font("Arial", "", 11)
        self.set_text_color(*DARK)
        indent = 8
        for i, item in enumerate(items, 1):
            self.set_x(self.l_margin)
            self.cell(indent, 6, f"{i}.", new_x="RIGHT", new_y="TOP")
            self.multi_cell(self.epw - indent, 6, item, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def callout(self, heading: str, text: str):
        bx, bw = 22, 168
        by = self.get_y()
        # estimate height: heading line + body lines
        body_lines = max(2, len(text) // 72 + 2)
        bh = 7 + body_lines * 5.8 + 5
        self.set_fill_color(*LIGHT_BG)
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.rect(bx, by, bw, bh, "FD")
        self.set_xy(bx + 4, by + 3)
        self.set_font("Arial", "B", 10)
        self.set_text_color(*TEAL)
        self.cell(0, 5, heading, new_x="LMARGIN", new_y="NEXT")
        self.set_x(bx + 4)
        self.set_font("Arial", "", 10)
        self.set_text_color(*DARK)
        self.multi_cell(bw - 8, 5.5, text)
        self.ln(4)

    def table(self, rows: list[tuple[str, str]], col1: int = 55):
        col2 = self.epw - col1
        for label, value in rows:
            self.set_x(self.l_margin)
            self.set_fill_color(*LIGHT_BG)
            self.set_font("Arial", "B", 10)
            self.set_text_color(*BROWN)
            self.cell(col1, 7, label, fill=True, border="B", new_x="RIGHT", new_y="TOP")
            self.set_font("Arial", "", 10)
            self.set_text_color(*DARK)
            self.multi_cell(col2, 7, value, border="B", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)


# ------------------------------------------------------------------
def build(doc: GuideDoc):

    # == Cover =========================================================
    doc.add_page()
    doc.set_fill_color(*CREAM)
    doc.rect(0, 0, 210, 297, "F")

    doc.ln(38)
    doc.set_font("Arial", "B", 32)
    doc.set_text_color(*BROWN)
    doc.multi_cell(0, 13, "HyperAgents", align="C")

    doc.ln(2)
    doc.set_font("Arial", "", 14)
    doc.set_text_color(*TEAL)
    doc.multi_cell(0, 7, "A Plain-English Guide for Everyone", align="C")

    doc.ln(8)
    doc.set_draw_color(*BROWN)
    doc.set_line_width(1.2)
    doc.line(50, doc.get_y(), 160, doc.get_y())

    doc.ln(12)
    doc.set_font("Arial", "I", 11)
    doc.set_text_color(*MUTED)
    doc.multi_cell(0, 6, "Research Prototype  |  github.com/AISmithy/hyperagents", align="C")

    doc.ln(18)
    doc.callout(
        "Who is this for?",
        "This guide is written for anyone who is curious about HyperAgents -- "
        "no coding experience needed. If you can use a web browser, you can "
        "follow along.",
    )

    # == 1. What Is HyperAgents? =======================================
    doc.add_page()
    doc.h1("1. What Is HyperAgents?")
    doc.body(
        "Imagine you are a student trying to improve at chess. You practise, "
        "you lose, you learn, you get better. Now imagine that instead of just "
        "getting better at chess, you ALSO get better at HOW you study chess. "
        "That is the core idea behind HyperAgents."
    )
    doc.body(
        "HyperAgents is a research tool that builds a software 'agent' -- a "
        "program that makes decisions -- and then lets that agent improve BOTH "
        "its decisions AND the method it uses to improve. In other words, "
        "it learns how to learn."
    )
    doc.callout(
        "The Big Idea in One Sentence",
        "A HyperAgent does not just get smarter over time -- it also improves "
        "the process that makes it smarter.",
    )

    doc.h2("What problem does it solve?")
    doc.body(
        "In this project the agent's job is to look at a software repository "
        "(think of it like a folder of code files on GitHub) and decide: "
        "Is this code good enough to approve, or should it be sent back for "
        "improvement?"
    )
    doc.body("Each repository is rated on five qualities:")
    doc.table([
        ("Maintainability", "How easy is it to read, understand, and change the code?"),
        ("Security",        "How protected is the code against hackers and bugs?"),
        ("Test Coverage",   "Does the code have tests that check it works correctly?"),
        ("Documentation",   "Are there clear instructions explaining what the code does?"),
        ("Simplicity",      "Is the code clean and focused, or unnecessarily complex?"),
    ])
    doc.body(
        "Each quality is scored from 0 (terrible) to 1 (perfect). The agent "
        "uses these five scores to vote ACCEPT or REJECT. Over many rounds, "
        "it gets better and better at making the right call."
    )

    # == 2. How Does It Work? ==========================================
    doc.add_page()
    doc.h1("2. How Does It Work?")

    doc.h2("Two brains inside one agent")
    doc.body(
        "Every HyperAgent has two decision-making systems working together:"
    )
    doc.table([
        ("Task Brain", "Decides ACCEPT or REJECT for each code repository."),
        ("Meta Brain", "Decides HOW the Task Brain should improve next round."),
    ])
    doc.body(
        "Most AI systems only have the first brain. HyperAgents is special "
        "because the Meta Brain can also improve itself -- the student becomes "
        "a better student."
    )

    doc.h2("The improvement loop -- step by step")
    doc.numbered([
        "Start with a basic agent that is about 65% accurate -- it makes "
        "mistakes on borderline cases on purpose.",
        "The agent tries a small change to itself (a 'mutation'), guided by "
        "what kinds of mistakes it has been making.",
        "The changed version is tested on all repositories.",
        "The result is always saved, even if it was worse -- so the system "
        "can come back to it later as a stepping stone.",
        "The Meta Brain updates its own strategy -- if things improved, it "
        "makes smaller changes next round (exploit); if not, it tries bolder "
        "moves (explore).",
        "Repeat 30-40 times. The agent typically reaches 85-95% accuracy.",
    ])

    doc.callout(
        "Why keep the bad versions too?",
        "Sometimes the best path to a right answer goes through a wrong answer "
        "first. By keeping every version ever tried (the 'archive'), the system "
        "can backtrack and try a different route -- like keeping your rough "
        "drafts when writing an essay.",
    )

    doc.h2("Three experiment modes")
    doc.body("The project lets you compare three setups side by side:")
    doc.table([
        ("HyperAgent",  "Full system -- both brains improve, all versions kept. (Best result)"),
        ("Baseline",    "Meta Brain is frozen. Only the Task Brain improves. (Middle result)"),
        ("No Archive",  "No history kept -- always starts from the current best. (Weakest)"),
    ])
    doc.body(
        "Running all three helps researchers understand which part of the "
        "system is responsible for the improvement."
    )

    # == 3. Accounts and Repositories ==================================
    doc.add_page()
    doc.h1("3. Accounts and Repositories")

    doc.h2("What is an 'account'?")
    doc.body(
        "In the real world, code lives in accounts -- a company like Google "
        "or a university lab might have hundreds of code repositories under "
        "one account name. HyperAgents lets you add accounts so the agent "
        "has more examples to learn from."
    )
    doc.body("Each account has a quality profile that shapes its repositories:")
    doc.table([
        ("Premium",          "High-quality org -- most repos pass review."),
        ("Startup",          "Fast-moving team -- quality varies widely."),
        ("Legacy",           "Older codebase -- lower security and test coverage."),
        ("Academic",         "Research code -- great docs, mixed everything else."),
        ("Security Focused", "Audit-grade security across all repos."),
        ("Mixed",            "Completely random -- useful as a control group."),
    ], col1=52)

    doc.h2("Synthetic vs GitHub accounts")
    doc.table([
        ("Synthetic",
         "The app generates realistic fake repositories instantly. "
         "Same account name always gives the same repos."),
        ("GitHub",
         "Enter a real GitHub username (e.g. 'torvalds') and the app "
         "fetches their public repos and scores them automatically."),
    ])

    doc.callout(
        "Why add more accounts?",
        "More repositories = more training examples = a smarter agent. "
        "Start with 15 repos from a 'startup' account and 15 from a 'premium' "
        "account, apply them to the dataset, and watch the agent's accuracy "
        "improve faster.",
    )

    # == 4. The Dashboard ==============================================
    doc.add_page()
    doc.h1("4. The Dashboard -- What You See")

    doc.body(
        "When you open the app in your web browser you see a tabbed dashboard. "
        "Here is what each tab does:"
    )

    doc.h2("Overview tab")
    doc.bullet([
        "Shows the best agent found so far and its accuracy scores.",
        "Lets you choose which experiment mode to run (HyperAgent, Baseline, "
        "or No Archive).",
        "Has Run and Reset buttons.",
        "Displays a live stats strip: iterations completed, archive size, "
        "training dataset size, best train accuracy, best test accuracy.",
    ])

    doc.h2("Accounts tab")
    doc.bullet([
        "Add a new account by typing a name and choosing Synthetic or GitHub.",
        "Pick how many repositories to scan (1 to 50).",
        "Click 'Add & Scan' -- the repos appear instantly.",
        "Click 'View Repos' on any account to see each repository's five "
        "feature scores as coloured bars (red = low, green = high).",
        "Click 'Apply All to Dataset' to teach the agent with all account "
        "repos, then Reset to start a fresh learning run.",
    ])

    doc.h2("Archive tab")
    doc.body(
        "Shows every agent version ever created, sorted by fitness. Each row "
        "shows the agent ID, which iteration it was created, its accuracy, "
        "and which agent it descended from."
    )

    doc.h2("Agent Detail tab")
    doc.body(
        "Click any agent in the Archive to inspect it here. You see the "
        "exact importance weights it gives to each feature, its "
        "accept/reject threshold, and notes it wrote to itself during its "
        "lifetime."
    )

    doc.h2("Runs tab")
    doc.body(
        "Every experiment is saved automatically. This tab lists all saved "
        "runs with their dates and final scores. You can reload any past run "
        "to compare it with a new one, or export the data as a CSV file "
        "(openable in Excel or Google Sheets)."
    )

    doc.h2("Live Review tab")
    doc.body(
        "Enter the URL of any GitHub repository and the agent will analyse "
        "it in real time and give it a score and an ACCEPT / REJECT verdict."
    )

    # == 5. Quick Start Walkthrough ====================================
    doc.add_page()
    doc.h1("5. Quick Start Walkthrough")

    doc.callout(
        "Before you begin",
        "Someone needs to start the app first (usually a technical person). "
        "Once it is running, open your web browser and go to: "
        "http://127.0.0.1:4173  --  you should see the HyperAgents dashboard.",
    )

    doc.h2("Your first experiment (about 5 minutes)")
    doc.numbered([
        "Go to the Accounts tab. Type 'my-startup' in the Account Name box. "
        "Leave Platform as Synthetic and choose the 'startup' profile. "
        "Set Repos to Scan to 15. Click 'Add & Scan'.",
        "Click 'View Repos' under the account you just created. You will see "
        "15 repositories with coloured bars for each quality score.",
        "Add a second account: name 'top-tier-org', profile 'premium', 15 repos.",
        "Click 'Apply All to Dataset'. The stats bar now shows a larger "
        "training size (e.g. '50 train repos (+30)').",
        "Go to the Overview tab. Make sure the mode is set to 'HyperAgent'. "
        "Click Reset, then click Run (30 iterations is a good starting point).",
        "Watch the Best Train and Best Test percentages climb with each "
        "iteration. A typical run reaches 85-95% accuracy.",
        "Switch to the Archive tab. You will see 30 agent versions listed. "
        "Click any row to jump to the Agent Detail tab and inspect its weights.",
        "Go to the Runs tab. Your experiment has been saved. "
        "Click 'Export CSV' to download the raw numbers.",
    ])

    doc.h2("Comparing the three modes")
    doc.numbered([
        "Note the final accuracy from your HyperAgent run.",
        "On the Overview tab, change mode to Baseline. "
        "Click Reset, then Run again with the same number of iterations.",
        "Repeat once more with No Archive mode.",
        "Go to the Runs tab. You now have three saved experiments. "
        "Compare the best test accuracy column -- "
        "HyperAgent should score highest, No Archive the lowest.",
    ])

    # == 6. Glossary ===================================================
    doc.add_page()
    doc.h1("6. Glossary")
    doc.body("Key terms used in this project, explained in plain English:")
    doc.table([
        ("Agent",          "A program that looks at information and makes a decision."),
        ("Archive",        "The collection of every agent version ever tried -- "
                           "like a family tree of improvements."),
        ("Accuracy",       "The percentage of repositories the agent classifies correctly."),
        ("Baseline",       "A simpler experiment where the Meta Brain is switched off, "
                           "used for comparison."),
        ("Dataset",        "The collection of example repositories the agent learns from."),
        ("Evaluation",     "Testing the agent on repos it has never seen, to check it "
                           "really learned something useful."),
        ("Fitness",        "Another word for accuracy on training data -- higher is better."),
        ("Iteration",      "One round of: try a change, test it, save it."),
        ("Meta Brain",     "The part of the agent that controls HOW it improves."),
        ("Mutation",       "A small change applied to the agent to try to make it better."),
        ("Profile",        "A description of an account's typical code quality level."),
        ("Repository",     "A folder of code files -- one software project."),
        ("Seed",           "A starting number that makes random choices reproducible."),
        ("Task Brain",     "The part of the agent that makes ACCEPT / REJECT decisions."),
        ("Test Accuracy",  "Accuracy on repos the agent was never trained on -- "
                           "the truest measure of how well it learned."),
        ("Threshold",      "The minimum score a repository needs to be accepted."),
        ("Train Accuracy", "Accuracy on repos used for learning -- can be high "
                           "if the agent memorised them without truly understanding."),
        ("Weights",        "Numbers that say how important each quality score is "
                           "to the agent's final verdict."),
    ], col1=48)

    # == 7. FAQ ========================================================
    doc.add_page()
    doc.h1("7. Frequently Asked Questions")

    faqs = [
        ("Do I need to know how to code?",
         "Not at all. The dashboard is a normal website. You click buttons, "
         "watch numbers change, and read the results. No typing of code required."),

        ("Is my code or data uploaded anywhere?",
         "No. Everything runs on your own computer. Nothing is sent to an "
         "external server unless you specifically enable the optional OpenAI "
         "connection (which is off by default)."),

        ("What does 65% starting accuracy mean?",
         "The initial agent is set up to make mistakes on tricky, borderline "
         "repositories on purpose. That gives it room to improve -- if it "
         "started at 100% there would be nothing to learn."),

        ("Why does the No Archive mode do worse?",
         "Without the archive the agent can only look at the very best version "
         "it has found so far. Sometimes you need to temporarily get worse "
         "before you can get much better. The archive allows that. "
         "No Archive mode gets stuck on 'good enough' answers."),

        ("What is a 'seed'?",
         "Random experiments can give different results each time. A seed is "
         "a number that locks the randomness so the experiment is repeatable. "
         "Seed 7 will always give the same sequence of random choices."),

        ("Can I use a real GitHub account?",
         "Yes -- go to the Accounts tab, choose 'GitHub' as the platform, and "
         "type any public GitHub username. The app will fetch their public repos "
         "and score them automatically using information like stars, topics, "
         "and whether the repo has a wiki or pages site."),

        ("How long does a run take?",
         "On a normal laptop, 30 iterations takes about 2-5 seconds. "
         "Running all three experiment modes with 5 random seeds takes "
         "roughly 30-60 seconds total."),

        ("What do I do with the CSV export?",
         "Open it in Excel or Google Sheets. Each row is one iteration. "
         "You can chart the accuracy columns to see learning curves, or "
         "compare conditions by filtering on the 'condition' column."),

        ("What is the difference between train and test accuracy?",
         "Train accuracy is measured on examples the agent has seen before -- "
         "it can be high just because the agent memorised them. "
         "Test accuracy is measured on examples the agent has NEVER seen -- "
         "this is the true measure of whether it learned something real."),
    ]

    for q, a in faqs:
        doc.h2(q)
        doc.body(a)

    # == Back cover ====================================================
    doc.add_page()
    doc.set_fill_color(*CREAM)
    doc.rect(0, 0, 210, 297, "F")
    doc.ln(70)
    doc.set_font("Arial", "B", 20)
    doc.set_text_color(*BROWN)
    doc.multi_cell(0, 10, "Ready to explore?", align="C")
    doc.ln(6)
    doc.set_font("Arial", "", 12)
    doc.set_text_color(*DARK)
    doc.multi_cell(
        0, 7,
        "Open your browser, go to http://127.0.0.1:4173,\n"
        "and start your first HyperAgents experiment.",
        align="C",
    )
    doc.ln(14)
    doc.set_draw_color(*BROWN)
    doc.set_line_width(1.0)
    doc.line(55, doc.get_y(), 155, doc.get_y())
    doc.ln(10)
    doc.set_font("Arial", "I", 10)
    doc.set_text_color(*MUTED)
    doc.multi_cell(
        0, 6,
        "Based on the HyperAgents paper  |  arXiv:2603.19461v1\n"
        "Source code: github.com/AISmithy/hyperagents",
        align="C",
    )


# ------------------------------------------------------------------
if __name__ == "__main__":
    doc = GuideDoc()
    build(doc)
    doc.output(str(OUT))
    print(f"Saved -> {OUT}")
