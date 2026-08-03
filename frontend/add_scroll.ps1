import os
os.chdir('D:/managesys/frontend')

with open('src/style.css', 'r', encoding='utf-8') as f:
    content = f.read()

# Add scroll fix at the end
scroll_fix = '''

/* ==========================================
   布局滚动修复
   ========================================== */
.app-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.el-container {
  height: 100%;
}

.main-container {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
}

.app-main {
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
}
'''

content = content + scroll_fix

with open('src/style.css', 'w', encoding='utf-8') as f:
    f.write(content)

print('Scroll fix added to style.css!')
