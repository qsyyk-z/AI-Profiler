import openai
import json
import logging
from client import openai_client
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class skill_agent:
    def generate_skill(self, md_path):
        """
        从markdown文件中提取技能点和分组信息
        
        Args:
            md_path: markdown文件路径
            
        Returns:
            dict: 包含技能点和分组信息的字典
        """
        try:
            if not Path(md_path).exists():
                logger.error(f"文件不存在: {md_path}")
                raise FileNotFoundError(f"文件不存在: {md_path}")
            
            logger.info(f"开始读取markdown文件: {md_path}")
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            from config import example_format
            
            prompt = f"""
            你是一位教育专家，任务是从课程PPT内容中识别学生需要掌握的技能点，并将这些技能点分组(group)，请着重注意，每个技能点可以出现在多个group中。        
            每个group的目标是可以用一道选择或判断题目联合考察这一group内的所有或部分技能点，每个group必须至少含有3个技能点。
            每个group的类型(type)可以是：
            - Dependency：表示这一个group中的某些技能点是此group中某些其他技能点的前置条件或基础知识，故可以一起考查。
            - Progressive：表示这一个group中的技能点是关于某一知识的不同深度的内容，如"掌握某个知识的定义"、"理解这个知识的应用方法"等技能点就可以出现在同一个Progressive组中。
            - Contrast：表示这一个group中的技能点是关于某些知识的对比理解，如A和B是两个相对的知识点，那么"理解A"、"理解B"等技能点就可以出现在同一个Contrast组中。
            - Application：表示这一个group中的技能点是关于某些知识的实际应用，这些技能点可能是运用不同方法解决相同问题场景，也可能是运用同一种方法解决不同问题。
            - Related：表示这一个group中的技能点之间存在着不属于以上四种关系的相关性，也可以在同一道题目中考察。

            请基于以下PPT内容，提取出：
            1. 所有学生需要掌握的具体技能点列表，每个技能点应该以"能够..."的格式表述
            2. 将相关的技能点分组，每组包含：
               - 组ID（如Group1_Definition）
               - 组类型
               - 组目标（target，描述该组技能点的总体目标）
               - 包含的技能点ID列表
            
            参考格式：
            {example_format}
            
            请确保：
            - 技能点描述清晰、具体，聚焦于学生能够执行的能力
            - 技能点覆盖PPT中的所有核心概念和方法
            - 分组逻辑合理，便于出题时合并考查相关技能点
            - 输出必须是有效的JSON格式
            - 输出中skills应对应一个列表，其中每个元素的格式为：
            "0: 能够形式化定义上下文无关文法 G = (V, T, P, S) 的四个组成部分及其约束条件",
            - 首先输出所有的skills，再输出所有的groups
            
            PPT内容：
            ```
            {content}
            ```
            """
            
            logger.info("调用大模型提取技能点和分组信息...")
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位教育评估专家，擅长从教学内容中提取学习目标和技能点。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            
            response_content = response.choices[0].message.content
            logger.info("大模型调用完成，开始解析结果...")
            
            try:
                result = json.loads(response_content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\n(.*?)\n```', response_content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    json_match = re.search(r'\{(.*?)\}', response_content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        logger.error("无法从响应中提取有效的JSON")
                        raise Exception("无法从响应中提取有效的JSON")
            
            logger.info(f"成功提取技能点和分组信息，共提取{len(result.get('skills', []))}个技能点")
            return result
            
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"生成技能点时出错: {e}")
            raise
    
    def save_to_yaml(self, result, output_path):
        """
        将技能点结果保存为YAML文件
        
        Args:
            result: 包含技能点和分组信息的字典
            output_path: 输出YAML文件路径
        """
        try:
            import yaml
            
            output_dir = Path(output_path).parent
            output_dir.mkdir(exist_ok=True)
            
            # 确保skills在groups前面
            ordered_result_1 = {}
            ordered_result_2 = {}
            if 'skills' in result:
                ordered_result_1['skills'] = result['skills']
            if 'groups' in result:
                ordered_result_2['groups'] = result['groups']
            
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(ordered_result_1, f, allow_unicode=True, default_flow_style=False)
                yaml.dump(ordered_result_2, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"技能点信息已保存到: {output_path}")
            
        except Exception as e:
            logger.error(f"保存YAML文件时出错: {e}")
            raise
    
    def process_md_file(self, md_path, output_dir="outputs"):
        file_name = Path(md_path).stem
        output_path = Path(output_dir) / f"{file_name}_skills.yml"
        
        result = self.generate_skill(md_path)
        
        self.save_to_yaml(result, output_path)
        
        return str(output_path)