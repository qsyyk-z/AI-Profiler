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
from md2skills import skill_agent
from config import pdf_url

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        # 1. 使用OCR_client处理PDF并生成markdown
        ocr = OCR_client()
        md_path = ocr.extract_pdf_to_markdown(pdf_url)
        logger.info(f"处理完成，markdown文件保存在: {md_path}")
        
        # 2. 使用skill_agent从markdown提取技能点
        if md_path and os.path.exists(md_path):
            logger.info("开始提取技能点和分组信息...")
            skills_agent = skill_agent()
            output_path = skills_agent.process_md_file(md_path)
            logger.info(f"技能点提取完成，结果保存在: {output_path}")
        else:
            logger.error(f"markdown文件不存在或无法获取: {md_path}")
            
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    main()