import json

with open('data.json') as f:
    data = json.load(f)

notes = data.get('notes', [])
meta = data.get('meta', {})

print(f'总笔记数: {len(notes)}')
print(f'is_demo: {meta.get("is_demo", "?")}')
print()

real_count = 0
fake_count = 0
real_examples = []
fake_examples = []

for n in notes:
    link = n.get('link', '')
    note_id = n.get('note_id', '')
    title = n.get('title', '')
    # 真实笔记的note_id通常是24位hex，假的可能是 fake_ 开头或随机的
    if 'xiaohongshu.com' in link or 'xhslink.com' in link:
        real_count += 1
        if len(real_examples) < 5:
            real_examples.append(n)
    elif note_id.startswith('fake_') or 'example.com' in link or link == '':
        fake_count += 1
        if len(fake_examples) < 5:
            fake_examples.append(n)
    else:
        # 检查其他特征
        if len(note_id) == 24:
            real_count += 1
            if len(real_examples) < 5:
                real_examples.append(n)
        else:
            fake_count += 1
            if len(fake_examples) < 5:
                fake_examples.append(n)

print(f'真实笔记: {real_count}')
print(f'疑似假数据: {fake_count}')
print()

print('=== 真实笔记示例 ===')
for n in real_examples:
    print(f'  标题: {n.get("title","")[:60]}')
    print(f'  作者: {n.get("author","")} | 点赞: {n.get("liked_count","")}')
    print(f'  链接: {n.get("link","")[:80]}')
    print(f'  note_id: {n.get("note_id","")}')
    print()

print('=== 假数据示例 ===')
for n in fake_examples:
    print(f'  标题: {n.get("title","")[:60]}')
    print(f'  作者: {n.get("author","")} | 点赞: {n.get("liked_count","")}')
    print(f'  链接: {n.get("link","")[:80]}')
    print(f'  note_id: {n.get("note_id","")}')
    print()
