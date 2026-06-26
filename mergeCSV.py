import pandas as pd
import os
import glob
import tkinter as tk
from tkinter import filedialog, messagebox


def get_folder_path():
    # 初始化 tkinter 并隐藏主窗口
    root = tk.Tk()
    root.withdraw()

    # 强制让弹出框置顶
    root.attributes('-topmost', True)

    # 弹出文件夹选择框
    selected_path = filedialog.askdirectory(title="请选择包含 181 个 CSV 文件的文件夹")

    # 选完后销毁 root 窗口
    root.destroy()
    return selected_path


def merge_csv():
    # 1. 让用户选文件夹
    target_dir = get_folder_path()

    if not target_dir:
        print("❌ 未选择文件夹，程序退出。")
        return

    # 2. 查找所有的 csv 文件
    all_files = glob.glob(os.path.join(target_dir, "*.csv"))
    output_name = 'scilit_final_combined.csv'
    output_path = os.path.join(target_dir, output_name)

    # 排除掉输出文件本身
    all_files = [f for f in all_files if output_name not in f]

    if not all_files:
        messagebox.showwarning("警告", "所选文件夹内没有找到 CSV 文件！")
        return

    print(f"📂 已选择: {target_dir}")
    print(f"📊 发现 {len(all_files)} 个文件，准备合并...")

    # 3. 读取并合并
    df_list = []
    for i, file in enumerate(all_files):
        try:
            # 使用 utf-8-sig 处理 Scilit 导出的特殊字符
            df = pd.read_csv(file, encoding='utf-8-sig', on_bad_lines='skip')
            df_list.append(df)
            print(f"✅ 已加载 ({i + 1}/{len(all_files)}): {os.path.basename(file)}")
        except Exception as e:
            print(f"⚠️ 跳过错误文件 {file}: {e}")

    if df_list:
        # 合并数据
        final_df = pd.concat(df_list, axis=0, ignore_index=True)

        # 保存到用户选定的文件夹下
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        # 弹窗提示成功
        messagebox.showinfo("完成", f"合并成功！\n总行数: {len(final_df)}\n文件保存在: {output_path}")
        print(f"🎉 大功告成！最终行数: {len(final_df)}")
    else:
        print("❌ 没有可合并的数据。")


if __name__ == "__main__":
    merge_csv()