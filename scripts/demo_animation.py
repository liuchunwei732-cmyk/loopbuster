import asyncio
import sys
import time

# Simple ANSI color codes
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_agent(msg):
    print(f"🤖 {Colors.OKBLUE}[Agent]{Colors.ENDC} {msg}")

def print_tool(msg):
    print(f"🛠️  {Colors.OKCYAN}[Tool]{Colors.ENDC} {msg}")

def print_loopbuster(msg):
    print(f"🛡️  {Colors.WARNING}{Colors.BOLD}[LoopBuster]{Colors.ENDC} {msg}")

def print_system(msg):
    print(f"⚙️  {Colors.OKGREEN}[System]{Colors.ENDC} {msg}")

async def run_demo():
    print_system("Initializing Agent with LoopBuster protection...")
    time.sleep(1)
    
    print("\n--- NORMAL BEHAVIOR ---")
    print_agent("Let's search for 'latest AI news'")
    time.sleep(0.5)
    print_tool("Search result: 1. GPT-5 rumored... 2. Claude update...")
    time.sleep(0.5)
    print_agent("I will summarize this.")
    time.sleep(1)
    
    print("\n--- STUCK SCENARIO BEGINS ---")
    print_agent("Wait, I need more info. Action: Search(query='AI news 2026')")
    time.sleep(0.5)
    print_tool("Search API Error: Rate limit exceeded. Try again in 10s.")
    time.sleep(0.5)
    
    # Loop 1
    print_agent("I failed. Let me try exactly the same thing. Action: Search(query='AI news 2026')")
    time.sleep(0.5)
    print_tool("Search API Error: Rate limit exceeded.")
    time.sleep(0.5)
    
    # Loop 2
    print_agent("Action: Search(query='AI news 2026')")
    time.sleep(0.5)
    print_tool("Search API Error: Rate limit exceeded.")
    time.sleep(0.5)
    
    # Loop 3 - Intercepted!
    print_agent("Action: Search(query='AI news 2026')")
    time.sleep(0.2)
    print_loopbuster("🛑 CYCLE DETECTED! Semantic similarity threshold exceeded (0.98).")
    print_loopbuster("Action blocked to save tokens.")
    print_loopbuster("Alternative Suggestion: Use 'Wait' tool or change query significantly.")
    time.sleep(0.5)
    
    print_agent("Ah, I am stuck. I will wait for 10 seconds instead. Action: Wait(10)")
    time.sleep(0.5)
    print_tool("Waited 10 seconds.")
    time.sleep(0.5)
    print_agent("Action: Search(query='AI news 2026')")
    time.sleep(0.5)
    print_tool("Search result: 1. Agent frameworks booming...")
    print_system("Demo complete. Agent recovered successfully.")

if __name__ == "__main__":
    asyncio.run(run_demo())
