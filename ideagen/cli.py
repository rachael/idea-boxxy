"""Interactive CLI for the idea generator — the main user experience."""

import sys
import logging
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.text import Text
from rich.columns import Columns
from rich import box

from .engine import IdeaEngine
from .store import IdeaStore
from .models import AppIdea, Reaction

log = logging.getLogger(__name__)
console = Console()

REACTION_MAP = {
    "1": Reaction.LOVE,
    "2": Reaction.LIKE,
    "3": Reaction.MEH,
    "4": Reaction.DISLIKE,
    "s": Reaction.SAVE,
    "e": Reaction.EXPLORE,
}

REACTION_LABELS = {
    "1": "[bold red]Love it![/]",
    "2": "[green]Like[/]",
    "3": "[dim]Meh[/]",
    "4": "[red]Not for me[/]",
    "s": "[yellow]Save for later[/]",
    "e": "[cyan]Tell me more[/]",
}


class IdeaCLI:
    """Interactive brainstorming session powered by Claude."""

    def __init__(self, db_path: str = "data/ideagen.db"):
        self.store = IdeaStore(db_path=db_path)
        self.engine = IdeaEngine(self.store)
        self.session_id: Optional[int] = None
        self._generated_titles: list[str] = []
        self._ideas_generated = 0
        self._ideas_liked = 0

    def run(self) -> None:
        """Main entry point — starts an interactive brainstorming session."""
        self._print_welcome()
        self.session_id = self.store.start_session()

        try:
            self._main_loop()
        except KeyboardInterrupt:
            console.print("\n")
        finally:
            self._end_session()

    def _print_welcome(self) -> None:
        interests = self.store.get_top_interests(n=5)
        sessions = self.store.get_recent_sessions(limit=1)

        welcome = Text()
        welcome.append("IDEA BOXXY", style="bold magenta")
        welcome.append(" — App Idea Generator\n\n", style="dim")

        if interests:
            welcome.append("Your interests: ", style="bold")
            welcome.append(", ".join(interests) + "\n", style="cyan")
        else:
            welcome.append("First time? I'll learn what you like as we go.\n", style="italic")

        if sessions:
            s = sessions[0]
            welcome.append(f"Last session: {s.ideas_generated} ideas, {s.ideas_liked} liked\n",
                           style="dim")

        console.print(Panel(welcome, border_style="magenta", padding=(1, 2)))

    def _main_loop(self) -> None:
        while True:
            action = self._prompt_action()

            if action == "generate":
                self._generate_round()
            elif action == "direction":
                self._choose_direction()
            elif action == "freeform":
                self._freeform_direction()
            elif action == "saved":
                self._show_saved()
            elif action == "profile":
                self._show_profile()
            elif action == "quit":
                break

    def _prompt_action(self) -> str:
        console.print()
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("[bold cyan]g[/]", "Generate ideas (open exploration)")
        table.add_row("[bold cyan]d[/]", "Choose a direction (I'll suggest some)")
        table.add_row("[bold cyan]f[/]", "Free-form (type your own direction)")
        table.add_row("[bold cyan]s[/]", "View saved ideas")
        table.add_row("[bold cyan]p[/]", "View my interest profile")
        table.add_row("[bold cyan]q[/]", "Quit")
        console.print(Panel(table, title="[bold]What next?[/]", border_style="blue"))

        choice = Prompt.ask(
            "[bold]Choose[/]",
            choices=["g", "d", "f", "s", "p", "q"],
            default="g",
        )

        return {
            "g": "generate", "d": "direction", "f": "freeform",
            "s": "saved", "p": "profile", "q": "quit",
        }[choice]

    def _generate_round(self, direction: Optional[str] = None) -> None:
        """Generate ideas and let user react to each one."""
        with console.status("[bold cyan]Brainstorming ideas...[/]", spinner="dots"):
            ideas = self.engine.generate_ideas(
                count=3,
                direction=direction,
                session_id=self.session_id,
                avoid_similar_to=self._generated_titles,
            )

        if not ideas:
            console.print("[red]Hmm, couldn't generate ideas. Try a different direction.[/]")
            return

        self._generated_titles.extend(i.title for i in ideas)
        self._ideas_generated += len(ideas)

        for i, idea in enumerate(ideas, 1):
            self._present_idea(idea, index=i, total=len(ideas))
            reaction = self._get_reaction()

            if reaction == "skip":
                continue
            elif reaction == "quit":
                return

            self.engine.process_reaction(idea, reaction)
            if reaction in ("love", "like", "save"):
                self._ideas_liked += 1

            if reaction == "explore":
                self._ideas_liked += 1
                self._explore_idea(idea)

        # Periodically infer deeper interests
        if self._ideas_generated >= 6 and self._ideas_generated % 6 == 0:
            with console.status("[dim]Learning your preferences...[/]", spinner="dots"):
                inferred = self.engine.infer_interests()
            if inferred:
                topics = [i["topic"] for i in inferred]
                console.print(
                    f"[dim italic]I'm picking up on: {', '.join(topics)}[/]"
                )

    def _choose_direction(self) -> None:
        """Suggest directions and let user pick one."""
        with console.status("[bold cyan]Thinking of directions...[/]", spinner="dots"):
            directions = self.engine.suggest_directions()

        console.print("\n[bold]Suggested directions:[/]")
        for i, d in enumerate(directions, 1):
            console.print(f"  [bold cyan]{i}[/] {d}")
        console.print(f"  [bold cyan]c[/] Custom direction")

        choice = Prompt.ask(
            "[bold]Pick a direction[/]",
            choices=[str(i) for i in range(1, len(directions) + 1)] + ["c"],
        )

        if choice == "c":
            self._freeform_direction()
        else:
            direction = directions[int(choice) - 1]
            self.store.log_direction(self.session_id, direction)
            console.print(f"\n[bold magenta]Exploring: {direction}[/]")
            self._generate_round(direction=direction)

    def _freeform_direction(self) -> None:
        """Let user type any direction they want."""
        direction = Prompt.ask("[bold]What direction interests you?[/]")
        if not direction.strip():
            return
        self.store.log_direction(self.session_id, direction)
        console.print(f"\n[bold magenta]Exploring: {direction}[/]")
        self._generate_round(direction=direction)

    def _present_idea(self, idea: AppIdea, index: int, total: int) -> None:
        """Display an idea card."""
        content = Text()
        content.append(f"{idea.one_liner}\n\n", style="italic")
        content.append(idea.description + "\n\n")
        content.append("Market: ", style="bold")
        content.append(idea.market_angle + "\n")
        content.append("For you: ", style="bold")
        content.append(idea.personal_angle + "\n")
        content.append("Users: ", style="bold")
        content.append(idea.target_users + "\n")
        content.append("Revenue: ", style="bold")
        content.append(idea.monetization + "\n")
        content.append("Complexity: ", style="bold")
        content.append(idea.complexity + "\n")

        if idea.tags:
            content.append("\n")
            for tag in idea.tags:
                content.append(f" {tag} ", style="on dark_blue")
                content.append(" ")

        title = f"[bold]{idea.title}[/] [{idea.category}] ({index}/{total})"
        console.print()
        console.print(Panel(content, title=title, border_style="green", padding=(1, 2)))

    def _get_reaction(self) -> str:
        """Prompt user for a reaction to an idea."""
        reaction_bar = " | ".join(
            f"[bold]{k}[/]={label}" for k, label in REACTION_LABELS.items()
        )
        console.print(f"  {reaction_bar}  |  [dim]n=skip  q=back[/]")

        choice = Prompt.ask(
            "  [bold]React[/]",
            choices=list(REACTION_MAP.keys()) + ["n", "q"],
            default="n",
        )

        if choice == "n":
            return "skip"
        elif choice == "q":
            return "quit"
        return REACTION_MAP[choice].value

    def _explore_idea(self, idea: AppIdea) -> None:
        """Deep-dive into a specific idea."""
        with console.status("[bold cyan]Diving deeper...[/]", spinner="dots"):
            details = self.engine.explore_idea(idea)

        content = []

        if "expanded_description" in details:
            content.append(f"## Overview\n{details['expanded_description']}\n")

        if "key_features" in details:
            features = "\n".join(f"- {f}" for f in details["key_features"])
            content.append(f"## Key Features\n{features}\n")

        if "tech_stack" in details:
            content.append(f"## Tech Stack\n{details['tech_stack']}\n")

        if "mvp_scope" in details:
            content.append(f"## MVP Scope\n{details['mvp_scope']}\n")

        if "differentiators" in details:
            content.append(f"## What Makes It Unique\n{details['differentiators']}\n")

        if "challenges" in details:
            challenges = "\n".join(f"- {c}" for c in details["challenges"])
            content.append(f"## Challenges\n{challenges}\n")

        if "similar_apps" in details:
            similar = "\n".join(f"- {a}" for a in details["similar_apps"])
            content.append(f"## Similar Apps\n{similar}\n")

        if "revenue_potential" in details:
            content.append(f"## Revenue Potential\n{details['revenue_potential']}\n")

        console.print(Panel(
            Markdown("\n".join(content)),
            title=f"[bold]Deep Dive: {idea.title}[/]",
            border_style="cyan",
            padding=(1, 2),
        ))

        # Ask if they want to save after exploring
        if Confirm.ask("  [bold]Save this idea?[/]", default=True):
            self.store.react_to_idea(idea.id, "save")
            console.print("  [green]Saved![/]")

    def _show_saved(self) -> None:
        """Display all saved/loved ideas."""
        saved = self.store.get_saved_ideas()
        if not saved:
            console.print("[dim]No saved ideas yet. Generate some and react with 's' or '1'![/]")
            return

        table = Table(title="Saved Ideas", box=box.ROUNDED, border_style="yellow")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", style="bold")
        table.add_column("One-liner")
        table.add_column("Category", style="cyan")
        table.add_column("Complexity", style="green")

        for idea in saved:
            table.add_row(
                str(idea.id), idea.title, idea.one_liner,
                idea.category, idea.complexity,
            )

        console.print(table)

        # Let user explore a saved idea
        if Confirm.ask("\n[bold]Explore a saved idea in detail?[/]", default=False):
            idea_id = Prompt.ask("[bold]Enter idea #[/]")
            try:
                idea = self.store.get_idea(int(idea_id))
                if idea:
                    self._explore_idea(idea)
                else:
                    console.print("[red]Idea not found.[/]")
            except ValueError:
                console.print("[red]Invalid idea number.[/]")

    def _show_profile(self) -> None:
        """Display the user's interest profile."""
        interests = self.store.get_interests(min_weight=0.05, limit=20)
        if not interests:
            console.print("[dim]No interests learned yet. React to some ideas first![/]")
            return

        table = Table(title="Your Interest Profile", box=box.ROUNDED, border_style="magenta")
        table.add_column("Topic", style="bold")
        table.add_column("Strength", justify="right")
        table.add_column("Source", style="dim")
        bar_width = 20

        for interest in interests:
            filled = int(interest.weight * bar_width)
            bar = "[green]" + "█" * filled + "[/][dim]" + "░" * (bar_width - filled) + "[/]"
            table.add_row(
                interest.topic,
                f"{bar} {interest.weight:.0%}",
                interest.source,
            )

        console.print(table)

        directions = self.store.get_direction_history(limit=5)
        if directions:
            console.print("\n[bold]Recent directions explored:[/]")
            for d in directions:
                console.print(f"  [dim]•[/] {d['direction']}")

    def _end_session(self) -> None:
        if self.session_id:
            self.store.update_session_stats(
                self.session_id, self._ideas_generated, self._ideas_liked
            )
            self.store.end_session(self.session_id)

        console.print(Panel(
            f"[bold]Session complete![/]\n"
            f"Ideas generated: {self._ideas_generated}\n"
            f"Ideas liked/saved: {self._ideas_liked}",
            border_style="magenta",
            padding=(1, 2),
        ))


def main():
    """Entry point for the idea generator CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Idea Boxxy — App Idea Generator")
    parser.add_argument("--db", default="data/ideagen.db", help="Database path")
    args = parser.parse_args()

    cli = IdeaCLI(db_path=args.db)
    cli.run()
