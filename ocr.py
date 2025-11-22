import os
import logging
import requests
import time
import json
import zipfile
import io
from pathlib import Path
from config import api_token

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OCR_client:
    def __init__(self, output_dir="mid_results"):
        self.output_dir = output_dir
        self.api_token = api_token
        self.api_url = "https://mineru.net/api/v4/extract/task"
        self.status_url = "https://mineru.net/api/v4/extract/task/{task_id}"  # 假设状态查询URL格式
        Path(output_dir).mkdir(exist_ok=True)
    
    def extract_pdf_to_markdown(self, pdf_path: str) -> str:
        """
        通过mineru API从PDF文件中提取文本并转换为markdown格式
        注意：API需要PDF文件的URL
            
        Args:
            pdf_path: PDF文件的URL
            
        Returns:
            str: 生成的markdown文件路径
        """
        try:
            if not pdf_path.startswith(('http://', 'https://')):
                raise ValueError(f"输入的不是url: {pdf_path}")
            
            if not self.api_token:
                logger.error("未提供API token，请在config.py中设置api_token")
                raise ValueError("未提供API token，请在config.py中设置api_token")
            
            logger.info(f"开始处理PDF URL: {pdf_path}")
            file_name = pdf_path.split('/')[-1].split('.')[0]
            
            # 准备请求头和数据
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }
            
            data = {
                "url": pdf_path,
                "model_version": "vlm"
            }
            
            # 发送创建任务请求
            logger.info(f"发送PDF提取请求到mineru API")
            response = requests.post(self.api_url, headers=headers, json=data)
            
            if response.status_code != 200:
                logger.error(f"API调用失败，状态码: {response.status_code}, 响应: {response.text}")
                raise Exception(f"API调用失败，状态码: {response.status_code}, 响应: {response.text}")
            
            result = response.json()
            
            # 检查响应状态
            if result.get("code") != 0:
                logger.error(f"API返回错误: {result.get('msg')}")
                raise Exception(f"API返回错误: {result.get('msg')}")
            
            # 获取任务ID
            task_id = result.get("data", {}).get("task_id")
            if not task_id:
                logger.error(f"无法从响应中获取task_id: {result}")
                raise Exception(f"无法从响应中获取task_id: {result}")
            
            logger.info(f"成功创建任务，task_id: {task_id}")
            
            # 轮询任务状态
            logger.info("开始轮询任务状态...")
            while True:
                # 查询任务状态
                task_status = self._get_task_status(task_id, headers)
                
                if task_status.get("code") != 0:
                    logger.error(f"获取任务状态失败: {task_status.get('msg')}")
                    raise Exception(f"获取任务状态失败: {task_status.get('msg')}")
                
                task_data = task_status.get("data", {})
                state = task_data.get("state")
                
                # 检查是否有错误
                if task_data.get("err_msg"):
                    logger.error(f"任务执行错误: {task_data.get('err_msg')}")
                    raise Exception(f"任务执行错误: {task_data.get('err_msg')}")
                
                # 显示进度信息
                if "extract_progress" in task_data:
                    progress = task_data["extract_progress"]
                    extracted = progress.get("extracted_pages", 0)
                    total = progress.get("total_pages", 0)
                    if total > 0:
                        logger.info(f"处理进度: {extracted}/{total} 页 ({int(extracted/total*100)}%)")
                
                # 检查任务状态
                if state == "done":
                    logger.info("任务已完成")
                    # 获取zip文件URL
                    zip_url = task_data.get("full_zip_url")
                    if not zip_url:
                        logger.error("任务完成但未找到zip文件URL")
                        raise Exception("任务完成但未找到zip文件URL")
                    
                    # 下载并处理zip文件
                    output_path = os.path.join(self.output_dir, f"{file_name}.md")
                    self._download_and_extract_markdown(zip_url, output_path)
                    return output_path
                
                elif state == "failed":
                    logger.error("任务执行失败")
                    raise Exception("任务执行失败")
                
                # 任务仍在进行中，继续轮询
                logger.info(f"任务状态: {state}，等待...")
                time.sleep(5)  # 5秒后再次查询
                
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            logger.error("请检查网络连接和API端点是否正确")
            raise
        except Exception as e:
            logger.error(f"处理PDF文件时出错: {e}")
            raise
    
    def _get_task_status(self, task_id, headers):
        """
        查询任务状态
        
        Args:
            task_id: 任务ID
            headers: 请求头
            
        Returns:
            dict: 任务状态响应
        """
        url = self.status_url.format(task_id=task_id)
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取任务状态时出错: {e}")
            # 返回错误响应
            return {"code": 1, "msg": str(e), "data": {}}
    
    def _download_and_extract_markdown(self, zip_url, output_path):
        """
        下载zip文件并提取markdown内容
        
        Args:
            zip_url: zip文件URL
            output_path: 输出markdown文件路径
        """
        try:
            logger.info(f"开始下载zip文件: {zip_url}")
            response = requests.get(zip_url)
            response.raise_for_status()
            
            # 读取zip文件内容
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                # 查找markdown文件
                md_files = [f for f in zip_ref.namelist() if f.endswith('.md')]
                
                if not md_files:
                    logger.error("在zip文件中未找到markdown文件")
                    raise Exception("在zip文件中未找到markdown文件")
                
                # 选择第一个markdown文件
                md_file = md_files[0]
                logger.info(f"找到markdown文件: {md_file}")
                
                # 读取markdown内容
                with zip_ref.open(md_file) as f:
                    md_content = f.read().decode('utf-8')
                
                # 保存到输出路径
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
                logger.info(f"markdown文件已保存到: {output_path}")
                
        except Exception as e:
            logger.error(f"下载和提取markdown文件时出错: {e}")
            raise
    
    def batch_extract(self, pdf_urls: list) -> list:
        """
        批量处理PDF文件URL列表
        
        Args:
            pdf_urls: PDF文件URL列表
            
        Returns:
            list: 生成的markdown文件路径列表
        """
        logger.info(f"开始批量处理，共 {len(pdf_urls)} 个URL")
        
        result_files = []
        for pdf_url in pdf_urls:
            try:
                md_file = self.extract_pdf_to_markdown(pdf_url)
                result_files.append(md_file)
            except Exception as e:
                logger.error(f"处理URL {pdf_url} 失败: {e}")
                continue
        
        logger.info(f"批量处理完成，成功生成 {len(result_files)} 个markdown文件")
        return result_files