import os
import re
import json
import yaml
import asyncio
import argparse
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import openai

from client import openai_client
from ocr import OCR_client

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 从环境变量或配置文件获取API token
def get_api_token():
    # 优先从环境变量获取
    token = os.environ.get('MINERU_API_TOKEN')
    
    # 如果环境变量中没有，尝试从配置文件读取
    if not token:
        config_path = Path('config.py')
        if config_path.exists():
            try:
                # 简单的配置文件解析
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                    # 尝试提取API token
                    token_match = re.search(r'MINERU_API_TOKEN\s*=\s*["\'](.*?)["\']', config_content)
                    if token_match:
                        token = token_match.group(1)
            except Exception as e:
                logger.warning(f"读取配置文件失败: {e}")
    
    # 如果仍然没有token，提示用户
    if not token:
        logger.warning("未找到MINERU_API_TOKEN，请确保已设置环境变量或在config.py中配置")
    
    return token

def main():
    try:
        # 获取API token
        api_token = get_api_token()
        
        # 创建OCR客户端
        ocr_client = OCR_client(output_dir="mid_results", api_token=api_token)
        
        # 注意：根据API的要求，本地PDF文件可能需要先上传到可访问的URL
        # 这里暂时直接使用本地路径，但可能需要根据API的实际要求进行调整
        pdf_path = "knowledges/lecture02.pdf"
        logger.info(f"开始处理PDF文件: {pdf_path}")
        
        # 检查文件是否存在
        if not os.path.exists(pdf_path):
            logger.error(f"PDF文件不存在: {pdf_path}")
            return 1
        
        # 调用提取方法
        md_path = ocr_client.extract_pdf_to_markdown(pdf_path)
        logger.info(f"处理完成，markdown文件保存在: {md_path}")
        
        return 0
        
    except ValueError as e:
        if "API token" in str(e):
            logger.error("错误: 缺少有效的API token")
            logger.error("请通过以下方式之一设置API token:")
            logger.error("1. 设置环境变量: set MINERU_API_TOKEN=your_token")
            logger.error("2. 在config.py中添加: MINERU_API_TOKEN = 'your_token'")
        else:
            logger.error(f"值错误: {e}")
        return 1
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        return 1

if __name__ == "__main__":
    # 运行主函数并返回退出码
    exit_code = main()
    import sys
    sys.exit(exit_code)