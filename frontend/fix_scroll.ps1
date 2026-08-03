import re

with open('D:/managesys/frontend/src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the main container style
old_style = """.main-container {
  display: flex;
  flex-direction: column;
}"""

new_style = """.main-container {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}"""

content = content.replace(old_style, new_style)

# Fix the app-main style
old_main = """.app-main {
  padding: 20px;
  overflow-y: auto;
  background: var(--app-bg-page);
  flex: 1;
}"""

new_main = """.app-main {
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--app-bg-page);
  flex: 1;
  min-height: 0;
  height: 100%;
}"""

content = content.replace(old_main, new_main)

with open('D:/managesys/frontend/src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed scroll issue in MainLayout.vue')
