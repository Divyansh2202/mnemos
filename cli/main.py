import os
import sys
import shutil
import subprocess
import requests
import typer
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich         import print as rprint

app     = typer.Typer(help="MnemOS — Universal Memory for AI Apps")
console = Console()

BASE_URL = os.getenv("MNEMOS_URL", "http://localhost:8765")


# ─── INIT ─────────────────────────────────────────────────────

@app.command()
def init():
    """Set up MnemOS config and .env file interactively."""
    import json as _json
    console.print(Panel("[bold cyan]MnemOS Setup[/bold cyan]", expand=False))

    project_dir = os.path.join(os.path.dirname(__file__), "..")
    env_path    = os.path.join(project_dir, ".env")
    example     = os.path.join(os.path.dirname(__file__), "..", ".env.example")

    if os.path.exists(env_path):
        console.print("[yellow].env already exists, skipping.[/yellow]")
    else:
        shutil.copy(example, env_path)
        console.print(f"[green]✓ Created .env[/green]")

    # ── Choose extraction engine ──
    console.print("\n[bold]Step 1: Choose extraction engine[/bold]")
    console.print("  [cyan]1[/cyan]  Gemini 2.5 Flash  (fast, cloud, needs API key)")
    console.print("  [cyan]2[/cyan]  Ollama            (local, private, needs GPU/CPU)")
    engine_choice = typer.prompt("Engine", default="1")
    engine = "gemini" if engine_choice.strip() in ("1", "gemini") else "ollama"

    gemini_key = ""
    chosen_model = "qwen2.5:3b"

    if engine == "gemini":
        gemini_key = typer.prompt("Gemini API key (from aistudio.google.com)", default="")
        if gemini_key:
            # write to .env
            with open(env_path) as f:
                content = f.read()
            if "GEMINI_API_KEY" in content:
                import re as _re
                content = _re.sub(r"GEMINI_API_KEY=.*", f"GEMINI_API_KEY={gemini_key}", content)
            else:
                content += f"\nGEMINI_API_KEY={gemini_key}\n"
            with open(env_path, "w") as f:
                f.write(content)
            console.print("[green]✓ Gemini key saved[/green]")
    else:
        # ── Choose Ollama model ──
        console.print("\n[bold]Step 2: Choose Ollama model[/bold]")
        t = Table("", "Model", "Size", "Notes", show_header=True, header_style="bold cyan")
        for i, (mname, msize, mnotes) in enumerate(POPULAR_MODELS, 1):
            t.add_row(str(i), mname, msize, mnotes)
        console.print(t)
        model_choice = typer.prompt("Pick a model (number or name)", default="3")
        try:
            idx = int(model_choice) - 1
            chosen_model = POPULAR_MODELS[idx][0]
        except (ValueError, IndexError):
            chosen_model = model_choice.strip() or "qwen2.5:3b"

        console.print(f"\n[cyan]Selected: {chosen_model}[/cyan]")
        if typer.confirm("Download it now?", default=True):
            ollama_bin = _find_ollama()
            if ollama_bin:
                console.print(f"[cyan]Downloading {chosen_model}...[/cyan]")
                subprocess.run([ollama_bin, "pull", chosen_model])
                console.print(f"[green]✓ {chosen_model} ready[/green]")
            else:
                console.print("[yellow]Ollama not found. Run: mnemos install-ollama first[/yellow]")

    # ── Save config ──
    config_path = os.path.join(project_dir, "mnemos_config.json")
    config = {"mode": engine, "gen_model": chosen_model}
    with open(config_path, "w") as f:
        _json.dump(config, f, indent=2)
    console.print(f"[green]✓ Config saved → {engine}" + (f" / {chosen_model}" if engine == "ollama" else "") + "[/green]")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Start PostgreSQL:  [cyan]mnemos db-start[/cyan]")
    if engine == "ollama":
        console.print("  2. Start Ollama:      [cyan]mnemos serve-ollama[/cyan]")
    console.print("  3. Start server:      [cyan]mnemos start[/cyan]")
    console.print("  4. Check health:      [cyan]mnemos doctor[/cyan]")
    console.print(f"\n  Switch model later:   [cyan]mnemos model --list[/cyan]")


# ─── DB ───────────────────────────────────────────────────────

@app.command(name="db-start")
def db_start():
    """Start PostgreSQL via Docker Compose."""
    compose = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
    console.print("[cyan]Starting PostgreSQL...[/cyan]")
    result = subprocess.run(
        ["docker", "compose", "-f", compose, "up", "-d"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        console.print("[green]✓ PostgreSQL is running on port 5432[/green]")
    else:
        console.print(f"[red]✗ Failed:[/red] {result.stderr}")
        raise typer.Exit(1)


# ─── INSTALL OLLAMA ───────────────────────────────────────────

@app.command(name="install-ollama")
def install_ollama():
    """Download and install Ollama locally (no sudo needed)."""
    import platform
    import stat

    system = platform.system().lower()
    machine = platform.machine().lower()

    if system != "linux":
        console.print("[yellow]Auto-install only supports Linux.[/yellow]")
        console.print("Download manually from: [cyan]https://ollama.com/download[/cyan]")
        return

    arch = "amd64" if machine in ("x86_64", "amd64") else "arm64"

    # Get latest release tag from GitHub API
    try:
        rel = requests.get(
            "https://api.github.com/repos/ollama/ollama/releases/latest",
            timeout=10
        ).json()
        tag = rel["tag_name"]
    except Exception:
        tag = "v0.19.0"  # fallback

    url = f"https://github.com/ollama/ollama/releases/download/{tag}/ollama-linux-{arch}.tar.zst"

    install_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(install_dir, exist_ok=True)
    archive     = os.path.join(install_dir, "ollama.tar.zst")
    ollama_bin  = os.path.join(install_dir, "ollama")

    console.print(f"[cyan]Downloading Ollama {tag} ({arch})...[/cyan]")
    try:
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(archive, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        print(f"\r  {pct}% ({downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB)", end="", flush=True)
        print()
    except Exception as e:
        console.print(f"[red]✗ Download failed: {e}[/red]")
        return

    # Extract tar.zst → find ollama binary inside
    console.print("[cyan]Extracting...[/cyan]")
    extract_dir = os.path.join(install_dir, "_ollama_extract")
    os.makedirs(extract_dir, exist_ok=True)
    result = subprocess.run(
        ["tar", "--use-compress-program=unzstd", "-xf", archive, "-C", extract_dir],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Try without unzstd
        result = subprocess.run(
            ["tar", "-xf", archive, "-C", extract_dir],
            capture_output=True, text=True
        )
    if result.returncode != 0:
        console.print(f"[red]✗ Extraction failed: {result.stderr}[/red]")
        console.print("[yellow]Tip: install zstd with: sudo apt install zstd[/yellow]")
        return

    # Find and move the ollama binary
    found_bin = None
    for root, dirs, files in os.walk(extract_dir):
        for fname in files:
            if fname == "ollama":
                found_bin = os.path.join(root, fname)
                break

    if not found_bin:
        console.print("[red]✗ Could not find ollama binary in archive[/red]")
        return

    shutil.move(found_bin, ollama_bin)
    shutil.rmtree(extract_dir, ignore_errors=True)
    os.remove(archive)

    os.chmod(ollama_bin, os.stat(ollama_bin).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    console.print(f"[green]✓ Ollama installed at {ollama_bin}[/green]")

    # Add to PATH hint
    shell_rc = os.path.expanduser("~/.bashrc")
    path_line = 'export PATH="$HOME/.local/bin:$PATH"'
    with open(shell_rc) as f:
        if path_line not in f.read():
            with open(shell_rc, "a") as fw:
                fw.write(f"\n{path_line}\n")
            console.print(f"[green]✓ Added ~/.local/bin to PATH in ~/.bashrc[/green]")

    console.print("\n[bold]Run:[/bold] [cyan]source ~/.bashrc && mnemos serve-ollama[/cyan]")


# ─── SERVE OLLAMA ─────────────────────────────────────────────

@app.command(name="serve-ollama")
def serve_ollama():
    """Start Ollama server in the background."""
    ollama_bin = _find_ollama()
    if not ollama_bin:
        console.print("[red]Ollama not found. Run: mnemos install-ollama[/red]")
        raise typer.Exit(1)

    console.print("[cyan]Starting Ollama server...[/cyan]")
    subprocess.Popen(
        [ollama_bin, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    import time; time.sleep(2)
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.ok:
            console.print("[green]✓ Ollama is running on port 11434[/green]")
    except Exception:
        console.print("[yellow]Ollama starting... wait a moment then run: mnemos pull-models[/yellow]")


# ─── PULL MODELS ──────────────────────────────────────────────

@app.command(name="pull-models")
def pull_models():
    """Pull required Ollama models (bge-m3 + qwen2.5:3b)."""
    ollama_bin = _find_ollama()
    if not ollama_bin:
        console.print("[red]Ollama not found. Run: mnemos install-ollama[/red]")
        raise typer.Exit(1)

    models = ["bge-m3", "qwen2.5:3b"]
    for model in models:
        console.print(f"[cyan]Pulling {model}...[/cyan]")
        result = subprocess.run([ollama_bin, "pull", model])
        if result.returncode == 0:
            console.print(f"[green]✓ {model} ready[/green]")
        else:
            console.print(f"[red]✗ Failed to pull {model}[/red]")


def _find_ollama() -> str | None:
    """Find ollama binary in PATH or ~/.local/bin."""
    # Check system PATH
    found = shutil.which("ollama")
    if found:
        return found
    # Check local install
    local = os.path.expanduser("~/.local/bin/ollama")
    if os.path.isfile(local):
        return local
    return None


# ─── START ────────────────────────────────────────────────────

@app.command()
def start(
    host: str = typer.Option("localhost", help="Host to bind"),
    port: int = typer.Option(8765,        help="Port to listen on"),
    reload: bool = typer.Option(False,    help="Auto-reload on code changes"),
):
    """Start the MnemOS server."""
    console.print(Panel(
        f"[bold green]Starting MnemOS[/bold green]\n"
        f"[dim]http://{host}:{port}[/dim]",
        expand=False
    ))
    root = os.path.join(os.path.dirname(__file__), "..")
    cmd  = [
        sys.executable, "-m", "uvicorn",
        "server.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd, cwd=root)


# ─── DOCTOR ───────────────────────────────────────────────────

@app.command()
def doctor():
    """Check if all components are working."""
    console.print(Panel("[bold]MnemOS Health Check[/bold]", expand=False))
    all_ok = True

    # 1. MnemOS server
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        if r.status_code == 200:
            console.print("[green]✓ MnemOS server[/green]   running")
        else:
            console.print("[red]✗ MnemOS server[/red]   not responding")
            all_ok = False
    except Exception:
        console.print("[red]✗ MnemOS server[/red]   not running  →  run: mnemos start")
        all_ok = False

    # 2. Ollama binary
    ollama_bin = _find_ollama()
    if ollama_bin:
        console.print(f"[green]✓ Ollama binary[/green]    found at {ollama_bin}")
    else:
        console.print("[red]✗ Ollama binary[/red]    not found  →  run: mnemos install-ollama")
        all_ok = False

    # 3. Ollama server
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            console.print(f"[green]✓ Ollama server[/green]    running  ({len(models)} models)")
            for needed in ["bge-m3", "qwen2.5:3b"]:
                found = any(needed in m for m in models)
                icon  = "[green]✓[/green]" if found else "[red]✗[/red]"
                hint  = "" if found else f"  →  run: mnemos pull-models"
                console.print(f"  {icon} {needed}{hint}")
                if not found:
                    all_ok = False
        else:
            console.print("[red]✗ Ollama server[/red]    not responding")
            all_ok = False
    except Exception:
        console.print("[red]✗ Ollama server[/red]    not running  →  run: mnemos serve-ollama")
        all_ok = False

    # 3. Docker / PostgreSQL
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=mnemos", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    if "mnemos" in result.stdout:
        console.print("[green]✓ PostgreSQL[/green]       running")
    else:
        console.print("[red]✗ PostgreSQL[/red]       not running  →  run: mnemos db-start")
        all_ok = False

    console.print()
    if all_ok:
        console.print("[bold green]All systems go![/bold green]")
    else:
        console.print("[bold red]Some issues found. Fix them above.[/bold red]")


# ─── STATS ────────────────────────────────────────────────────

@app.command()
def stats():
    """Show memory store statistics."""
    try:
        r = requests.get(f"{BASE_URL}/stats", timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        console.print(f"[red]Could not reach MnemOS server: {e}[/red]")
        raise typer.Exit(1)

    console.print(Panel("[bold]MnemOS Stats[/bold]", expand=False))
    console.print(f"Total memories: [bold cyan]{data['total_memories']}[/bold cyan]")

    if data.get("by_type"):
        t = Table("Type", "Count", show_header=True)
        for k, v in data["by_type"].items():
            t.add_row(k, str(v))
        console.print(t)

    if data.get("by_app"):
        t = Table("App", "Count", show_header=True)
        for k, v in data["by_app"].items():
            t.add_row(k, str(v))
        console.print(t)


# ─── LIST ─────────────────────────────────────────────────────

@app.command(name="list")
def list_memories(
    user_id: str = typer.Option("default", help="User ID"),
    limit:   int = typer.Option(20,        help="Max memories to show"),
):
    """List stored memories."""
    try:
        r = requests.get(
            f"{BASE_URL}/memory/all",
            params={"user_id": user_id, "limit": limit},
            timeout=5
        )
        r.raise_for_status()
        memories = r.json()["memories"]
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not memories:
        console.print("[yellow]No memories found.[/yellow]")
        return

    t = Table("ID", "Content", "Type", "Confidence", "App", show_header=True)
    for m in memories:
        t.add_row(
            m["id"][:16],
            m["content"][:60],
            m["type"],
            f"{m['confidence']:.2f}",
            m["app_id"],
        )
    console.print(t)


# ─── SEARCH ───────────────────────────────────────────────────

@app.command()
def search(
    query:   str = typer.Argument(..., help="Search query"),
    user_id: str = typer.Option("default", help="User ID"),
    limit:   int = typer.Option(5,         help="Max results"),
):
    """Semantic search through memories."""
    try:
        r = requests.post(
            f"{BASE_URL}/memory/retrieve",
            json={"query": query, "user_id": user_id, "limit": limit},
            timeout=10
        )
        r.raise_for_status()
        memories = r.json()["memories"]
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not memories:
        console.print("[yellow]No matching memories found.[/yellow]")
        return

    t = Table("Content", "Type", "Relevance", "App", show_header=True)
    for m in memories:
        t.add_row(
            m["content"][:70],
            m["type"],
            f"{m['relevance']:.3f}",
            m["app_id"],
        )
    console.print(t)


# ─── MODEL ────────────────────────────────────────────────────

POPULAR_MODELS = [
    ("qwen2.5:0.5b", "0.4 GB", "Fastest, lowest quality"),
    ("qwen2.5:1.5b", "1.0 GB", "Fast, decent quality"),
    ("qwen2.5:3b",   "1.9 GB", "Balanced (default)"),
    ("qwen2.5:7b",   "4.7 GB", "Good quality"),
    ("qwen2.5:14b",  "9.0 GB", "High quality"),
    ("qwen2.5:32b",  "20 GB",  "Very high quality"),
    ("llama3.2:3b",  "2.0 GB", "Meta Llama 3.2"),
    ("mistral:7b",   "4.1 GB", "Mistral 7B"),
    ("phi3:mini",    "2.2 GB", "Microsoft Phi-3 Mini"),
]

@app.command()
def model(
    engine: str = typer.Option(None, "--engine", "-e", help="Extraction engine: gemini or ollama"),
    name:   str = typer.Option(None, "--name",   "-n", help="Ollama model name e.g. qwen2.5:7b"),
    pull:   str = typer.Option(None, "--pull",   "-p", help="Download an Ollama model e.g. qwen2.5:7b"),
    list_models: bool = typer.Option(False, "--list", "-l", help="List downloaded + popular models"),
):
    """View or set the extraction engine and model."""

    # ── pull / download a model ──
    if pull:
        ollama_bin = _find_ollama()
        if not ollama_bin:
            console.print("[red]Ollama not found. Run: mnemos install-ollama[/red]")
            raise typer.Exit(1)
        console.print(f"[cyan]Downloading {pull} ...[/cyan]")
        result = subprocess.run([ollama_bin, "pull", pull])
        if result.returncode == 0:
            console.print(f"[green]✓ {pull} downloaded[/green]")
            console.print(f"\nNow set it: [cyan]mnemos model --engine ollama --name {pull}[/cyan]")
        else:
            console.print(f"[red]✗ Failed to download {pull}[/red]")
        return

    # ── show available Ollama models ──
    if list_models:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        downloaded = set()
        try:
            r = requests.get(f"{ollama_url}/api/tags", timeout=5)
            downloaded = {m["name"] for m in r.json().get("models", [])}
        except Exception:
            pass

        console.print(Panel("[bold]Ollama Models[/bold]", expand=False))
        t = Table("Model", "Size", "Notes", "Downloaded", show_header=True, header_style="bold cyan")
        for mname, msize, mnotes in POPULAR_MODELS:
            dl = "[green]✓[/green]" if any(mname in d for d in downloaded) else "[dim]—[/dim]"
            t.add_row(mname, msize, mnotes, dl)
        console.print(t)
        console.print("\n[dim]Download a model:[/dim]  [cyan]mnemos model --pull qwen2.5:7b[/cyan]")
        return

    # ── apply config change ──
    if engine or name:
        payload = {}
        if engine:
            if engine not in ("gemini", "ollama"):
                console.print("[red]Engine must be 'gemini' or 'ollama'[/red]")
                raise typer.Exit(1)
            payload["mode"] = engine
        if name:
            # check if model is downloaded, offer to pull if not
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            try:
                r = requests.get(f"{ollama_url}/api/tags", timeout=5)
                downloaded = [m["name"] for m in r.json().get("models", [])]
                if not any(name in d for d in downloaded):
                    console.print(f"[yellow]'{name}' is not downloaded yet.[/yellow]")
                    if typer.confirm(f"Download it now?", default=True):
                        ollama_bin = _find_ollama()
                        if ollama_bin:
                            subprocess.run([ollama_bin, "pull", name])
                        else:
                            console.print("[red]Ollama not found. Run: mnemos install-ollama[/red]")
                            raise typer.Exit(1)
            except Exception:
                pass
            payload["gen_model"] = name
        try:
            r = requests.post(f"{BASE_URL}/config", json=payload, timeout=5)
            r.raise_for_status()
            cfg = r.json()
            console.print(f"[green]✓ Engine:[/green]  {cfg.get('mode')}")
            console.print(f"[green]✓ Model:[/green]   {cfg.get('gen_model')}")
        except Exception as e:
            console.print(f"[red]Could not update config: {e}[/red]")
            console.print("Is the MnemOS server running?  [cyan]mnemos start[/cyan]")
        return

    # ── show current config ──
    try:
        r = requests.get(f"{BASE_URL}/config", timeout=5)
        r.raise_for_status()
        cfg = r.json()
        console.print(Panel("[bold]Extraction Config[/bold]", expand=False))
        console.print(f"Engine : [cyan]{cfg.get('mode', '—')}[/cyan]")
        console.print(f"Model  : [cyan]{cfg.get('gen_model', '—')}[/cyan]")
        console.print("\n[dim]Commands:[/dim]")
        console.print("  [cyan]mnemos model --list[/cyan]                          show all models")
        console.print("  [cyan]mnemos model --pull qwen2.5:7b[/cyan]               download a model")
        console.print("  [cyan]mnemos model --engine ollama --name qwen2.5:7b[/cyan]  use a model")
        console.print("  [cyan]mnemos model --engine gemini[/cyan]                 switch to Gemini")
    except Exception as e:
        console.print(f"[red]Could not reach MnemOS server: {e}[/red]")


# ─── MCP SETUP ────────────────────────────────────────────────

@app.command(name="mcp-config")
def mcp_config():
    """Print Claude Desktop MCP config to paste into claude_desktop_config.json."""
    root      = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    python    = os.path.join(root, "myenv", "bin", "python")
    mcp_path  = os.path.join(root, "integrations", "mcp_server.py")

    config = {
        "mcpServers": {
            "mnemos": {
                "command": python,
                "args":    [mcp_path],
                "env": {
                    "MNEMOS_URL":     "http://localhost:8765",
                    "MNEMOS_USER_ID": "default"
                }
            }
        }
    }

    import json
    console.print(Panel("[bold]Claude Desktop MCP Config[/bold]", expand=False))
    console.print("Add this to [cyan]~/.config/claude/claude_desktop_config.json[/cyan]:\n")
    console.print(json.dumps(config, indent=2))
    console.print("\n[dim]Then restart Claude Desktop.[/dim]")


if __name__ == "__main__":
    app()
