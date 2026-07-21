import os
import re
import sys

def split_codex_into_articles(input_file, output_folder, codex_name):
    """
    Разбивает файл с кодексом на отдельные статьи и сохраняет их в папку output_folder.
    input_file: путь к txt-файлу с текстом кодекса
    output_folder: папка, куда сохранять статьи (уже должна существовать)
    codex_name: короткое название кодекса (например, 'ГК РФ')
    """
    # Читаем файл с попыткой разных кодировок
    text = None
    for encoding in ['utf-8', 'cp1251', 'latin-1']:
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                text = f.read()
            print(f"   Файл прочитан в кодировке {encoding}")
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError(f"Не удалось прочитать файл {input_file} ни в одной из кодировок")
    
    # Ищем все статьи по шаблону: "Статья 1.", "Статья 2.", и т.д.
    pattern = r'(Статья\s+\d+\.?\s*)'
    parts = re.split(pattern, text)
    
    articles = {}
    current_title = None
    current_text = []
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.match(r'^Статья\s+\d+\.?', part):
            if current_title is not None:
                articles[current_title] = '\n'.join(current_text).strip()
            current_title = part
            current_text = []
        else:
            current_text.append(part)
    
    if current_title is not None:
        articles[current_title] = '\n'.join(current_text).strip()
    
    os.makedirs(output_folder, exist_ok=True)
    
    for title, content in articles.items():
        match = re.search(r'Статья\s+(\d+)', title)
        if match:
            article_num = match.group(1)
            filename = f"{codex_name} ст.{article_num}.txt"
        else:
            filename = f"{codex_name} {title[:20]}.txt".replace(' ', '_')
        
        file_path = os.path.join(output_folder, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Сохранена статья: {filename}")

if __name__ == "__main__":
    import glob
    
    output_folder = "laws"
    txt_files = glob.glob("*.txt")
    
    for filepath in txt_files:
        codex_name = os.path.splitext(os.path.basename(filepath))[0]
        print(f"\n--- Обрабатываем: {filepath} (кодекс: {codex_name}) ---")
        split_codex_into_articles(filepath, output_folder, codex_name)
    
    print("\n✅ Все файлы обработаны!")