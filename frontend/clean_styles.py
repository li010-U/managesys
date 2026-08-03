import os
os.chdir('D:/managesys/frontend')

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the old duplicate app-main style
old_style = '''/* 主内容区 */
.app-main {
  padding: 20px;
  overflow-y: auto;
  background: var(--app-bg-page);
  flex: 1;
}


'''

new_style = '''/* 主内容区 */
.app-main {
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--app-bg-page);
  flex: 1;
  min-height: 0;
  height: 100%;
}

'''

content = content.replace(old_style, new_style)

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Removed duplicate styles!')
