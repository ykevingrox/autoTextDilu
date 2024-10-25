import dashscope
from dashscope import Generation
import logging
from typing import List, Dict
import os

class AIProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        dashscope.api_key = api_key

    def process_paper(self, paper_path: str) -> str:
        """处理单篇论文并返回AI分析结果"""
        logging.info(f"开始处理论文: {paper_path}")
        try:
            # 读取文件内容
            with open(paper_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logging.info(f"成功读取论文内容，长度: {len(content)} 字符")

            # 构建提示词
            prompt = """请分析这篇论文，并提供以下信息：
1. 主要研究问题
2. 研究方法
3. 主要发现
4. 创新点
5. 局限性

请用中文回答，并使用简洁的语言。
"""
            logging.info("正在调用通义千问API...")
            
            # 调用通义千问API
            response = Generation.call(
                model='qwen-max',
                prompt=prompt + "\n论文内容：\n" + content,
                max_tokens=1500,
                temperature=0.7,
                result_format='message'
            )
            
            logging.info(f"API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.output.text
                logging.info(f"API调用成功，返回结果长度: {len(result)} 字符")
                return result
            else:
                error_msg = f"API调用失败: {response.status_code}, 响应内容: {response}"
                logging.error(error_msg)
                return f"AI分析失败: {error_msg}"

        except Exception as e:
            error_msg = f"处理论文时发生错误: {str(e)}"
            logging.error(error_msg, exc_info=True)  # 添加完整的异常堆栈信息
            return f"处理失败: {str(e)}"

    def batch_process_papers(self, papers: List[Dict]) -> Dict[str, str]:
        """批量处理论文并返回结果字典"""
        logging.info(f"开始批量处理论文，共 {len(papers)} 篇")
        results = {}
        
        for i, paper in enumerate(papers, 1):
            paper_id = paper.get('id')
            logging.info(f"处理第 {i}/{len(papers)} 篇论文")
            logging.info(f"论文信息: ID={paper_id}, 标题={paper.get('title')}")
            
            if paper.get('downloaded', False):
                # 尝试不同的可能文件名
                possible_paths = [
                    os.path.join('downloads', paper_id),  # 无后缀
                    os.path.join('downloads', f"{paper_id}.pdf"),
                    os.path.join('downloads', f"{paper_id}.txt")
                ]
                
                # 查找存在的文件
                paper_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        paper_path = path
                        break
                
                if paper_path:
                    logging.info(f"找到论文文件: {paper_path}")
                    result = self.process_paper(paper_path)
                    results[paper_id] = result
                    logging.info(f"论文处理完成，结果长度: {len(result)} 字符")
                else:
                    logging.warning(f"未找到论文文件，尝试过以下路径: {possible_paths}")
            else:
                logging.warning(f"论文未下载，跳过处理: ID={paper_id}")
        
        logging.info(f"批量处理完成，成功处理 {len(results)} 篇论文")
        return results
