import os
import re
import asyncio
import subprocess
import signal
import logging
import json
import shlex
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- Configuration & Global Variables ---

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Directory setup
BASE_WORKSPACES_DIR = os.path.abspath("workspaces")
PROCESSES_FILE = "processes.json"
MAX_OUTPUT_LENGTH = 4000

# Bot state management
user_sessions = {}
running_processes = {}

# Flask app for Keep-Alive
flask_app = Flask(__name__)

# List of allowed shell commands for safety
ALLOWED_COMMANDS = [
    'ls', 'cat', 'head', 'tail', 'grep', 'find', 'wc', 'sort', 'uniq',
    'echo', 'pwd', 'mkdir', 'touch', 'cp', 'mv', 'rm', 'rmdir',
    'clear', 'date', 'whoami', 'file', 'diff', 'basename', 'dirname',
    'stat', 'du', 'tar', 'unzip', 'zip', 'gzip', 'gunzip', 'chmod',
    'git', 'curl', 'wget', 'pip', 'pip3', 'npm', 'npx', 'node',
    'python', 'python3', 'nohup', 'screen', 'nano', 'vim', 'vi',
    'less', 'more', 'awk', 'sed', 'cut', 'tr', 'tee', 'xargs',
    'ln', 'readlink', 'realpath', 'which', 'whereis', 'type',
    'env', 'export', 'set', 'unset', 'printenv',
    'df', 'free', 'top', 'htop', 'ps', 'kill', 'killall', 'pkill',
    'uptime', 'uname', 'hostname', 'id', 'groups', 'users',
    'history', 'alias', 'unalias', 'source', 'exec',
    'sleep', 'time', 'timeout', 'watch', 'cron', 'crontab', 'at',
    'ssh', 'scp', 'rsync', 'sftp', 'ftp', 'telnet', 'netstat', 'ss',
    'ping', 'traceroute', 'nslookup', 'dig', 'host', 'ifconfig', 'ip',
    'iptables', 'route', 'arp', 'netcat', 'nc', 'nmap',
    'apt', 'apt-get', 'yum', 'dnf', 'pacman', 'brew', 'snap',
    'dpkg', 'rpm', 'make', 'cmake', 'gcc', 'g++', 'clang',
    'java', 'javac', 'mvn', 'gradle', 'ant',
    'ruby', 'gem', 'bundle', 'rake', 'rails',
    'php', 'composer', 'artisan', 'laravel',
    'go', 'cargo', 'rustc', 'rustup',
    'perl', 'lua', 'swift', 'kotlin', 'scala',
    'docker', 'docker-compose', 'kubectl', 'helm', 'minikube',
    'systemctl', 'service', 'journalctl', 'dmesg',
    'chown', 'chgrp', 'umask', 'getfacl', 'setfacl',
    'cmp', 'comm', 'patch', 'strings', 'od', 'hexdump', 'xxd',
    'base64', 'md5sum', 'sha256sum', 'sha512sum', 'openssl',
    'ssh-keygen', 'ssh-copy-id', 'ssh-add', 'ssh-agent',
    'gpg', 'gpg2', 'pass',
    'jq', 'yq', 'xmllint', 'csvtool',
    'ffmpeg', 'convert', 'identify', 'mogrify',
    'pandoc', 'latex', 'pdflatex', 'xelatex',
    'sqlite3', 'mysql', 'psql', 'mongo', 'redis-cli',
    'screen', 'tmux', 'byobu', 'nohup', 'disown', 'bg', 'fg', 'jobs',
    'lsof', 'strace', 'ltrace', 'gdb', 'valgrind',
    'mount', 'umount', 'fdisk', 'parted', 'mkfs', 'fsck',
    'dd', 'sync', 'shred', 'wipe',
    'useradd', 'usermod', 'userdel', 'groupadd', 'groupmod', 'groupdel',
    'passwd', 'chpasswd', 'su', 'sudo',
    'crontab', 'at', 'batch', 'anacron',
    'logrotate', 'logger', 'syslog',
    'man', 'info', 'help', 'apropos', 'whatis',
    'cal', 'bc', 'dc', 'expr', 'factor', 'seq', 'shuf',
    'rev', 'tac', 'nl', 'fmt', 'fold', 'column', 'colrm', 'expand', 'unexpand',
    'split', 'csplit', 'paste', 'join', 'pr',
    'test', 'true', 'false', 'yes', 'no',
    'iconv', 'recode', 'convmv',
    'tree', 'ncdu', 'ranger', 'mc',
    'htpasswd', 'ab', 'siege', 'wrk',
    'certbot', 'letsencrypt',
    'yarn', 'pnpm', 'bun', 'deno',
    'ts-node', 'tsx', 'esbuild', 'webpack', 'vite', 'rollup', 'parcel',
    'pytest', 'unittest', 'nose', 'tox', 'coverage',
    'jest', 'mocha', 'chai', 'cypress', 'playwright',
    'eslint', 'prettier', 'black', 'flake8', 'pylint', 'mypy',
    'virtualenv', 'venv', 'pipenv', 'poetry', 'conda',
    'aws', 'gcloud', 'az', 'heroku', 'vercel', 'netlify', 'fly',
    'terraform', 'ansible', 'puppet', 'chef', 'vagrant',
]


# --- Flask Keep-Alive Server Functions ---

@flask_app.route('/')
def home():
    return "Telegram Bot Manager is Running 24/7! (Keep-Alive Active)"

@flask_app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}

def run_web_server():
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"Flask Web Server running on 0.0.0.0:{port}...")
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Flask Web Server Error: {e}")

def start_keep_alive():
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()


# --- Workspace and Session Management ---

def ensure_workspace(user_id: int) -> str:
    workspace_path = os.path.join(BASE_WORKSPACES_DIR, str(user_id))
    os.makedirs(workspace_path, exist_ok=True)
    return os.path.abspath(workspace_path)


def get_user_cwd(user_id: int) -> str:
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "cwd": ensure_workspace(user_id),
        }
    return user_sessions[user_id]["cwd"]


def set_user_cwd(user_id: int, new_cwd: str) -> bool:
    workspace = ensure_workspace(user_id)
    abs_path = os.path.abspath(new_cwd)
    
    # Security check: must be inside the workspace
    if not abs_path.startswith(workspace):
        return False
    
    if os.path.isdir(abs_path):
        user_sessions[user_id]["cwd"] = abs_path
        return True
    return False


def is_path_in_workspace(path: str, workspace: str, cwd: str) -> bool:
    if path.startswith('/'):
        resolved = os.path.abspath(os.path.join(workspace, path.lstrip('/')))
    else:
        resolved = os.path.abspath(os.path.join(cwd, path))
    return resolved.startswith(workspace)


def check_command_safety(command: str, workspace: str, cwd: str) -> tuple:
    # Restrict access to common sensitive system paths
    dangerous_patterns = [
        r'/etc/', r'/var/', r'/usr/', r'/bin/', r'/sbin/',
        r'/root', r'/home/runner(?!/workspace)', r'/proc/', r'/sys/', r'/dev/',
        r'\$\(', r'`.*`', # Block command substitution
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return False, "Access to sensitive system directories not allowed."
    
    try:
        parts = shlex.split(command)
    except ValueError:
        # Fallback for complex commands that shlex might fail on
        parts = command.split()
    
    if not parts:
        return False, "No command provided"
    
    base_cmd = parts[0]
    
    # Check against the allowed command list
    if base_cmd not in ALLOWED_COMMANDS:
        # Allow running scripts even if the executable name isn't whitelisted
        if not base_cmd.endswith('.py') and not base_cmd.endswith('.sh') and not base_cmd.endswith('.js'):
            return False, f"Command `{base_cmd}` not allowed.\n\nUse /commands to see allowed commands."
    
    # Check arguments for path traversal attempts (like '..' in paths)
    for arg in parts[1:]:
        if arg.startswith('-'):
            continue
        if '..' in arg:
            test_path = os.path.normpath(os.path.join(cwd, arg))
            if not test_path.startswith(workspace):
                return False, "Cannot access paths outside workspace."
    
    return True, ""


# --- Process Persistence Functions ---

def load_processes():
    global running_processes
    if os.path.exists(PROCESSES_FILE):
        try:
            with open(PROCESSES_FILE, 'r') as f:
                running_processes = json.load(f)
        except:
            running_processes = {}


def save_processes():
    with open(PROCESSES_FILE, 'w') as f:
        json.dump(running_processes, f, indent=2)


# --- Telegram Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_workspace(user_id)
    
    welcome_msg = """**VPS Bot - Full Terminal Access**

Welcome! You now have your own isolated VPS environment with 200+ commands.

**Terminal Commands:**
- Just type commands directly (`ls`, `cd`, `mkdir`, `git`, etc.)
- `cd <dir>` - Change directory
- `git clone <url>` - Clone repositories
- `pip install <pkg>` - Install Python packages
- `python3 script.py` - Run Python scripts

**File Operations:**
- `/upload` - Upload files
- `/download <file>` - Download files

**24/7 Bot Hosting:**
- `/run python3 bot.py` - Run a process 24/7
- `/stop <id>` - Stop a process
- `/ps` - List processes
- `/logs <id>` - View logs

**System Info:**
- `/sysinfo` - Show system information
- `/disk` - Show disk usage
- `/memory` - Show memory usage

**Other:**
- `/help` - Show this message
- `/myid` - Get your user ID
- `/commands` - List all allowed commands

Start typing commands!"""

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmds = sorted(ALLOWED_COMMANDS)
    categories = {
        "File Operations": ['ls', 'cat', 'head', 'tail', 'cp', 'mv', 'rm', 'mkdir', 'touch', 'find', 'tree'],
        "Text Processing": ['grep', 'awk', 'sed', 'cut', 'sort', 'uniq', 'wc', 'tr'],
        "Archives": ['tar', 'zip', 'unzip', 'gzip', 'gunzip'],
        "Network": ['curl', 'wget', 'ping', 'netstat', 'ssh', 'scp'],
        "Git": ['git'],
        "Package Managers": ['pip', 'pip3', 'npm', 'yarn', 'apt', 'apt-get'],
        "Languages": ['python', 'python3', 'node', 'ruby', 'go', 'java', 'php'],
        "Process": ['ps', 'kill', 'top', 'htop', 'nohup', 'screen', 'tmux'],
        "System": ['df', 'du', 'free', 'uptime', 'uname', 'whoami', 'date'],
    }
    
    response = "**Allowed Commands (200+):**\n\n"
    for category, sample_cmds in categories.items():
        available = [c for c in sample_cmds if c in cmds]
        if available:
            # Show a few examples from each category
            response += f"*{category}:* {', '.join(available[:5])}...\n"
    
    response += f"\n**Total: {len(cmds)} commands**\n"
    response += "\nType any command directly to execute!"
    
    await update.message.reply_text(response, parse_mode='Markdown')


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your User ID: `{user_id}`", parse_mode='Markdown')


async def sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        uname = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=10)
        uptime = subprocess.run(['uptime'], capture_output=True, text=True, timeout=10)
        
        info = f"**System Information:**\n```\n{uname.stdout}\n{uptime.stdout}```"
        await update.message.reply_text(info, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def disk_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        result = subprocess.run(['df', '-h'], capture_output=True, text=True, timeout=10)
        await update.message.reply_text(f"**Disk Usage:**\n```\n{result.stdout}```", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def memory_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        result = subprocess.run(['free', '-h'], capture_output=True, text=True, timeout=10)
        await update.message.reply_text(f"**Memory Usage:**\n```\n{result.stdout}```", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


def execute_command(user_id: int, command: str) -> tuple:
    cwd = get_user_cwd(user_id)
    workspace = ensure_workspace(user_id)
    
    command = command.strip()
    if not command:
        return "", "No command provided"
    
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.
