import shutil, os

src = r"e:\ilovendProject\Tide-Watcher\frontend"
dst = r"e:\ilovendProject\Tide-Watcher\archive\frontend_nextjs"

SKIP = {".next", "node_modules", ".pnpm-store"}

os.makedirs(dst, exist_ok=True)

def ignore(directory, files):
    return [f for f in files if f in SKIP]

shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
print(f"Copied to {dst} (skipped {SKIP})")

# Remove original
for item in os.listdir(src):
    path = os.path.join(src, item)
    if item in SKIP:
        continue
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
print("Original source files removed (build dirs kept for cleanup later)")
