import os
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from PIL import Image
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import shutil

# --- Placeholder helper ---
def add_placeholder(entry, placeholder_text):
    def on_focus_in(event):
        if entry.get() == placeholder_text:
            entry.delete(0, 'end')
            entry.config(fg='black')

    def on_focus_out(event):
        if entry.get() == '':
            entry.insert(0, placeholder_text)
            entry.config(fg='grey')

    entry.insert(0, placeholder_text)
    entry.config(fg='grey')
    entry.bind('<FocusIn>', on_focus_in)
    entry.bind('<FocusOut>', on_focus_out)

def get_book_root(url):
    parsed = urlparse(url)
    parts = parsed.path.rstrip('/').split('/')

    # Если последний элемент — файл (с точкой)
    if '.' in parts[-1]:
        # Если путь достаточно длинный и последние три части — это content/medium/filename.jpg
        if len(parts) >= 3 and parts[-3] == 'content' and parts[-2] == 'medium':
            parts = parts[:-3]
        else:
            # Если это html-файл, например html5forpc.html, то отрезаем только файл
            parts = parts[:-1]

    book_name = parts[-1] if parts else ''

    path_to_book = '/'.join(parts)
    root_url = parsed._replace(path=path_to_book, query="", fragment="").geturl()
    return root_url



def get_pages_count_from_xml(book_root_url):
    possible_paths = [
        "data/pages.xml",
        "pages.xml",
        "book/pages.xml"
    ]

    for path in possible_paths:
        xml_url = f"{book_root_url}/{path}"
        try:
            r = requests.get(xml_url, timeout=10)
            if r.status_code == 200 and "<pages" in r.text:
                root = ET.fromstring(r.content)
                pages = root.findall(".//page")
                if pages:
                    return len(pages)
        except Exception as e:
            print(f"Ошибка при чтении {xml_url}: {e}")
    return None

def on_toggle_all_pages():
    if var_all_pages.get():
        # Галочка поставлена — отключаем поля ввода диапазона
        entry_start.config(state=tk.DISABLED)
        entry_end.config(state=tk.DISABLED)
    else:
        # Галочка снята — включаем поля, и пытаемся подставить значения
        entry_start.config(state=tk.NORMAL)
        entry_end.config(state=tk.NORMAL)

        # Попытка считать страницы из ссылки
        link = entry_link.get().strip()
        if link and link != placeholder_text:
            book_root = get_book_root(link)
            max_pages = get_pages_count_from_xml(book_root)
            if max_pages is None:
                max_pages = 1000  # запасное значение

            entry_start.delete(0, tk.END)
            entry_start.insert(0, "1")

            entry_end.delete(0, tk.END)
            entry_end.insert(0, str(max_pages))

def on_link_change(event=None):
    # Если галочка снята, обновляем диапазон страниц по ссылке
    if not var_all_pages.get():
        on_toggle_all_pages()

def download_pages(book_root_url, start, end, save_as_pdf, folder, book_name, total_pages, progress_var, btn_download):
    if start == 1 and end == total_pages:
        save_folder_name = f"{book_name}_full"
    else:
        save_folder_name = f"{book_name}_{start}-{end}"

    save_path = os.path.join(folder, save_folder_name)
    os.makedirs(save_path, exist_ok=True)

    images = []
    for i in range(start, end + 1):
        page_url = f"{book_root_url}/content/pages/page{i}.jpg"
        print(f"Скачивание страницы {i}: {page_url}")
        try:
            r = requests.get(page_url, stream=True, timeout=10)
            if r.status_code != 200:
                print(f"Страница {i} не найдена (HTTP {r.status_code}), прекращаем загрузку.")
                break
            img_path = os.path.join(save_path, f"{i:03d}.jpg")
            with open(img_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            if save_as_pdf:
                images.append(Image.open(img_path).convert("RGB"))

            # Обновление прогресса
            progress = int(((i - start + 1) / (end - start + 1)) * 100)
            progress_var.set(progress)
        except Exception as e:
            print(f"Ошибка при загрузке страницы {i}: {e}")
            break

    if save_as_pdf and images:
        pdf_path = os.path.join(folder, f"{save_folder_name}.pdf")
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        print(f"PDF сохранён: {pdf_path}")

        # Удаляем папку с изображениями
        shutil.rmtree(save_path)
        print(f"Временная папка с изображениями удалена: {save_path}")

    else:
        print(f"Изображения сохранены в: {save_path}")

    messagebox.showinfo("Готово", "Загрузка завершена!")
    btn_download.config(state=tk.NORMAL)
    progress_var.set(0)

def start_download_thread():
    btn_download.config(state=tk.DISABLED)
    thread = threading.Thread(target=start_download)
    thread.start()

def start_download():
    link = entry_link.get().strip()
    if not link or link == placeholder_text:
        messagebox.showerror("Ошибка", "Введите ссылку!")
        btn_download.config(state=tk.NORMAL)
        return

    book_root = get_book_root(link)
    book_name = book_root.rstrip('/').split('/')[-1]

    total_pages = get_pages_count_from_xml(book_root)
    if total_pages is None:
        total_pages = 1000
        print("Не удалось определить точное число страниц, будет скачано до 1000 или пока не закончится.")
    else:
        print(f"Всего страниц по pages.xml: {total_pages}")

    if var_all_pages.get():
        start, end = 1, total_pages
    else:
        try:
            start = int(entry_start.get())
            end = int(entry_end.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректные номера страниц!")
            btn_download.config(state=tk.NORMAL)
            return

        if start < 1 or end < start or end > total_pages:
            messagebox.showerror("Ошибка", f"Неверный диапазон страниц! Максимум: {total_pages}")
            btn_download.config(state=tk.NORMAL)
            return

    folder = filedialog.askdirectory(title="Выберите папку для сохранения")
    if not folder:
        btn_download.config(state=tk.NORMAL)
        return

    save_as_pdf = (var_format.get() == "pdf")

    download_pages(book_root, start, end, save_as_pdf, folder, book_name, total_pages, progress_var, btn_download)

# ==== GUI ====
root = tk.Tk()
root.title("Скачиватель книг с https://mrf.museumart.ru/library")

tk.Label(root, text="Ссылка на книгу или страницу:").pack()

entry_link = tk.Entry(root, width=70)
entry_link.pack(pady=5)


placeholder_text = "www.vstavte_ssilku.ru"
add_placeholder(entry_link, placeholder_text)

var_all_pages = tk.BooleanVar(value=True)
chk_all = tk.Checkbutton(root, text="Скачать все страницы", variable=var_all_pages, command=on_toggle_all_pages)
chk_all.pack()

frame_range = tk.Frame(root)
tk.Label(frame_range, text="Начальная страница:").grid(row=0, column=0)
entry_start = tk.Entry(frame_range, width=5)
entry_start.grid(row=0, column=1, padx=5)
tk.Label(frame_range, text="Конечная страница:").grid(row=0, column=2)
entry_end = tk.Entry(frame_range, width=5)
entry_end.grid(row=0, column=3, padx=5)
frame_range.pack(pady=5)

# Сначала отключаем диапазон страниц, потому что галочка стоит
entry_start.config(state=tk.DISABLED)
entry_end.config(state=tk.DISABLED)

# Обработка вставки/изменения ссылки
entry_link.bind('<FocusOut>', on_link_change)  # по потере фокуса
entry_link.bind('<KeyRelease>', on_link_change)  # по изменению текста

tk.Label(root, text="Формат сохранения:").pack()
var_format = tk.StringVar(value="pdf")
tk.Radiobutton(root, text="PDF", variable=var_format, value="pdf").pack()
tk.Radiobutton(root, text="Изображения (JPG)", variable=var_format, value="jpg").pack()

progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
progress_bar.pack(fill='x', padx=10, pady=10)

btn_download = tk.Button(root, text="Скачать", command=start_download_thread)
btn_download.pack(pady=10)

root.mainloop()
