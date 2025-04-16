# -*- coding: utf-8 -*-
import requests
import json
import sys
import time
from typing import Set, Optional, Dict, List, Any
import os
from pathlib import Path
import traceback
import argparse


API_KEY_ENV = os.environ.get("QUAKE_API_KEY")



QUAKE_BASE_URL = "https://quake.360.net"
QUAKE_SEARCH_API_URL = f"{QUAKE_BASE_URL}/api/v3/search/quake_service"


CACHE_FILE = Path("quake_icp_cache_list.json")  #
ITERATION_BATCH_SIZE = 20
MAX_ITERATIONS = 100
ITERATION_DELAY = 0.2
RETRY_DELAY = 2.0


# --- 缓存处理函数 ---
def load_cache() -> Dict[str, Any]:

    global CACHE_FILE
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                print(f"[缓存] 正在加载缓存文件: {CACHE_FILE}")
                content = f.read()
                if not content:
                    print("[缓存] 缓存文件为空。")
                    return {}
                cache_data = json.loads(content)
                # --- 校验: 确保公司对应的值是列表 ---
                for company, data in cache_data.items():
                    if not isinstance(data, list):
                        print(f"[警告] 缓存中公司 '{company}' 的数据不是列表格式，将忽略此条目。", file=sys.stderr)
                        # 可以选择删除错误条目: del cache_data[company] 或 返回空字典
                        # 这里选择忽略，保留其他可能正确的条目
                return cache_data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[警告] 加载缓存文件 '{CACHE_FILE}' 失败: {e}。将创建新缓存。", file=sys.stderr)
        except Exception as e:
            print(f"[错误] 加载缓存时发生意外错误: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    else:
        print(f"[缓存] 缓存文件 '{CACHE_FILE}' 不存在，将创建新缓存。")
    return {}


def save_cache(cache_data: Dict[str, Any]):
    """保存缓存数据到文件"""
    global CACHE_FILE
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[错误] 保存缓存文件 '{CACHE_FILE}' 失败: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[错误] 保存缓存时发生意外错误: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


# --- 主查询函数 ---
def get_company_icp_info_cached_iterative(api_key: str, company_name: str) -> Optional[List[Dict[str, Any]]]:

    print("\n" + "=" * 10 + f" 开始查询: {company_name} " + "=" * 10)

    if not api_key:
        print("[错误] 未提供有效的 API Key。", file=sys.stderr)
        return None
    if not company_name or not company_name.strip():
        print("[错误] 公司名称无效。", file=sys.stderr)
        return None
    company_name = company_name.strip()


    full_cache = load_cache()

    cached_icp_list: List[Dict[str, Any]] = full_cache.get(company_name, [])


    initial_cached_domains: Set[str] = set(obj.get('domain') for obj in cached_icp_list if obj.get('domain'))

    session_domains: Set[str] = initial_cached_domains.copy()

    session_icp_list: List[Dict[str, Any]] = [item for item in cached_icp_list if item.get('licence')]  # 过滤掉可能无效的缓存项


    # 这个集合用于构建排除查询语句，仍然需要域名
    found_domains_for_exclusion: Set[str] = set(obj.get('domain') for obj in cached_icp_list if obj.get('domain'))
    print(
        f"[缓存] 加载到 {len(session_domains)} 个缓存备案记录 (对应 {len(found_domains_for_exclusion)} 个域名用于初始排除)。")


    found_mismatched_domains: Set[str] = set()

    new_record_added_to_session = False

    headers = {
        "X-QuakeToken": api_key,
        "Content-Type": "application/json"
    }
    base_query = f'service.http.icp.main_licence.unit:"{company_name}" AND _exists_:service.http.icp'


    for iteration in range(MAX_ITERATIONS):
        print(f"\n--- 开始第 {iteration + 1}/{MAX_ITERATIONS} 次迭代 ---")
        new_record_found_this_iteration = False  # 标记本轮循环是否发现新备案记录

        all_domains_to_exclude = found_domains_for_exclusion.union(found_mismatched_domains)
        exclude_clause = ""
        if all_domains_to_exclude:
            escaped_domains = [json.dumps(d) for d in all_domains_to_exclude]
            if len(all_domains_to_exclude) > 500:
                print(f"[警告] 排除列表包含 {len(all_domains_to_exclude)} 个域名，查询可能过长或性能低下！",
                      file=sys.stderr)
            exclude_clause = f' AND NOT (domain:{" OR domain:".join(escaped_domains)})'

        final_query = base_query + exclude_clause
        print(f"[*] 第 {iteration + 1} 次迭代查询 (排除 {len(all_domains_to_exclude)} 个已知域名)...")

        payload = {
            "query": final_query,
            "start": 0,
            "size": ITERATION_BATCH_SIZE,
            "ignore_cache": True,
            "latest": False
        }

        response = None
        try:
            if iteration > 0:
                time.sleep(ITERATION_DELAY)

            response = requests.post(QUAKE_SEARCH_API_URL, headers=headers, json=payload, timeout=60)
            result = response.json()
            api_code = result.get("code", -1)

            if api_code != 0:

                error_message = result.get('message', '未知 API 错误')
                print(f"[错误] Quake API 返回非成功状态: {error_message} (Code: {api_code})", file=sys.stderr)
                if str(api_code) == 'u3007':
                    print("[错误] 积分不足，终止查询。", file=sys.stderr)
                elif str(api_code) == 'q3005' or str(api_code) == 'u3005':
                    print(f"[警告] 遇到速率限制，等待 {RETRY_DELAY:.1f} 秒后重试本次迭代...")
                    time.sleep(RETRY_DELAY)
                    continue
                elif str(api_code).startswith('u3015') or str(api_code).startswith('q'):
                    print("[错误] 查询语句错误或服务器内部错误，终止查询。", file=sys.stderr)
                    print(f"[Debug] 查询语句前缀: {base_query}")
                else:
                    print("[错误] 未知 API 错误，终止查询。", file=sys.stderr)
                return None

            response.raise_for_status()

            data = result.get("data", [])
            count_in_batch = len(data)
            total_results_api = result.get("meta", {}).get("pagination", {}).get("total", 0)
            print(f"[*]   API 调用成功，返回 {count_in_batch} 条记录 (查询匹配总数: {total_results_api})。")

            if not data:
                print("[*]   本次迭代未返回任何新记录，查询结束。")
                break

            batch_new_records_count = 0
            batch_mismatched_domains_count = 0
            for i, item in enumerate(data):
                try:
                    icp_info = item['service']['http']['icp']
                    actual_unit = icp_info.get('main_licence', {}).get('unit')
                    icp_domain = icp_info.get("domain")
                    icp_licence = icp_info.get("licence")

                    # 校验关键字段是否存在且有效
                    if (not isinstance(icp_domain, str) or not icp_domain.strip() or icp_domain.replace('.',
                                                                                                        '').isdigit()
                            or not isinstance(icp_licence, str) or not icp_licence.strip()):
                        continue

                    if actual_unit == company_name:

                        if icp_domain not in session_domains:
                            batch_new_records_count += 1
                            session_domains.add(icp_domain)  # 加入已处理备案号集合
                            session_icp_list.append(icp_info)  # 加入结果列表
                            # --- 同时更新用于排除的域名集合 ---
                            found_domains_for_exclusion.add(icp_domain)

                            new_record_found_this_iteration = True  # 标记本轮有新发现
                            new_record_added_to_session = True  # 标记确实有新数据加入（用于最终缓存判断）
                    else:

                        if icp_domain not in found_mismatched_domains:
                            batch_mismatched_domains_count += 1
                            found_mismatched_domains.add(icp_domain)

                except (KeyError, TypeError):
                    continue

            print(
                f"[*]   本批次处理完毕：发现 {batch_new_records_count} 个新备案记录 (主体精确匹配)，发现 {batch_mismatched_domains_count} 个新的不匹配主体域名用于后续排除。")


            # if not new_record_found_this_iteration and count_in_batch > 0:
            #     print("[*]   本次迭代未发现新的 *目标公司* 备案记录，查询结束。")
            #     break
            if total_results_api <= ITERATION_BATCH_SIZE and not new_record_found_this_iteration:
                print("[*]   API报告的总匹配数已处理完毕，且未发现新的 *目标公司* 备案记录，查询结束。")

                break

        # ... (异常处理保持不变) ...
        except requests.exceptions.Timeout:
            print(f"[错误] 第 {iteration + 1} 次迭代请求超时。", file=sys.stderr)
            return None
        except requests.exceptions.RequestException as e:
            print(f"[错误] 第 {iteration + 1} 次迭代请求发生网络错误: {e}", file=sys.stderr)
            if response is not None: print(f"HTTP Status: {response.status_code}", file=sys.stderr)
            return None
        except json.JSONDecodeError:
            print(f"[错误] 第 {iteration + 1} 次迭代解析响应失败。", file=sys.stderr)
            if response: print(f"Raw text: {response.text[:500]}...")
            return None
        except Exception as e:
            print(f"[错误] 第 {iteration + 1} 次迭代处理时发生未知错误: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return None

    # --- 迭代循环结束 ---
    if iteration == MAX_ITERATIONS - 1:
        print(f"[警告] 已达到最大迭代次数 ({MAX_ITERATIONS})，可能未完全获取所有数据。", file=sys.stderr)

    # 3. 条件性更新缓存
    # --- 只有当 new_record_added_to_session 为 True 时才保存 ---
    if new_record_added_to_session:
        print(f"[缓存] 本次运行发现新备案记录，正在更新缓存 (共 {len(session_icp_list)} 条记录)...")
        # --- 修改点: 保存 session_icp_list (列表格式) ---
        full_cache[company_name] = session_icp_list
        save_cache(full_cache)  # 调用保存函数
    else:
        print(f"[缓存] 本次运行未发现新的备案记录，缓存文件 '{CACHE_FILE}' 未更新。")

    # --- 修改点: 返回 session_icp_list ---
    return session_icp_list


def summarize_cache_file():
    """加载并汇总打印缓存文件内容"""
    global CACHE_FILE  # 确保使用正确的缓存文件路径
    print("\n" + "=" * 20 + " 缓存文件内容汇总 " + "=" * 20)
    cache_data = load_cache()

    if not cache_data:
        print("[信息] 缓存文件为空或加载失败，无内容可汇总。")
        return

    total_companies = 0
    total_records = 0

    # 按公司名称排序输出
    for company_name in sorted(cache_data.keys()):
        icp_list = cache_data[company_name]
        print(f"\n--- 公司: {company_name} ---")
        total_companies += 1

        if not icp_list or not isinstance(icp_list, list):
            print("  [*] 无有效的备案记录。")
            continue

        # 按备案号排序
        try:
            sorted_icp_list = sorted(icp_list, key=lambda x: x.get('licence', ''))
        except Exception as e:
            print(f"  [警告] 尝试按备案号排序时出错: {e}。将按原顺序输出。", file=sys.stderr)
            sorted_icp_list = icp_list  # Fallback to original list

        print(f"  [*] 共找到 {len(sorted_icp_list)} 条备案记录:")
        for icp_info in sorted_icp_list:
            domain = icp_info.get('domain', 'N/A')
            licence = icp_info.get('licence', 'N/A')
            print(f"    - 域名: {domain:<40} 备案号: {licence}")  # 简单对齐
            total_records += 1

    print("\n" + "=" * 20 + " 缓存统计 " + "=" * 20)
    print(f"缓存中公司总数: {total_companies}")
    print(f"缓存中备案记录总数: {total_records}")
    print("=" * (44 + len(" 缓存统计 ")))


def search_cache(search_term: str):
    """在缓存中搜索公司名称或域名"""
    global CACHE_FILE
    print("\n" + "=" * 20 + f" 缓存搜索: '{search_term}' " + "=" * 20)
    cache_data = load_cache()
    search_term_lower = search_term.lower()  # 转换为小写进行不区分大小写搜索
    found_company = False
    found_domain = False

    if not cache_data:
        print("[信息] 缓存文件为空或加载失败，无法搜索。")
        print("=" * (44 + len(f" 缓存搜索: '{search_term}' ")))
        return

    # 1. 搜索公司名称
    print("\n--- 匹配的公司名称 ---")
    matched_companies = []
    for company_name in cache_data.keys():
        if search_term_lower in company_name.lower():
            matched_companies.append(company_name)
            found_company = True

    if matched_companies:
        # 按名称排序显示匹配的公司
        for company_name in sorted(matched_companies):
            print(f"\n[公司匹配] {company_name}")
            icp_list = cache_data.get(company_name, [])
            if icp_list and isinstance(icp_list, list):
                try:
                    sorted_icp_list = sorted(icp_list, key=lambda x: x.get('licence', ''))
                except Exception:
                    sorted_icp_list = icp_list
                print(f"  [*] 共 {len(sorted_icp_list)} 条备案记录:")
                for icp_info in sorted_icp_list:
                    domain = icp_info.get('domain', 'N/A')
                    licence = icp_info.get('licence', 'N/A')
                    print(f"    - 域名: {domain:<40} 备案号: {licence}")
            else:
                print("  [*] 无有效的备案记录。")
    else:
        print("未找到匹配的公司名称。")

    # 2. 搜索域名
    print("\n--- 匹配的域名 ---")
    matched_domains_info = []  # 存储元组 (域名, 公司名)
    for company_name, icp_list in cache_data.items():
        if icp_list and isinstance(icp_list, list):
            for icp_info in icp_list:
                domain = icp_info.get('domain')
                if domain and isinstance(domain, str) and search_term_lower in domain.lower():
                    matched_domains_info.append((domain, company_name))
                    found_domain = True

    if matched_domains_info:
        # 按域名排序显示匹配的域名及其公司
        for domain, company in sorted(matched_domains_info):
            print(f"[域名匹配] 域名: {domain:<40} 所属公司: {company}")
    else:
        print("未找到匹配的域名。")

    if not found_company and not found_domain:
        print(f"\n[结果] 在缓存中未找到与 '{search_term}' 匹配的公司名称或域名。")

    print("\n" + "=" * (44 + len(f" 缓存搜索: '{search_term}' ")))


# --- 主程序 (保持不变，处理返回的列表) ---
if __name__ == "__main__":
    # --- 设置命令行参数解析 ---
    parser = argparse.ArgumentParser(
        description="查询公司备案信息，支持缓存和迭代排除，并可汇总缓存内容。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # 添加查询相关的参数组
    query_group = parser.add_argument_group('查询选项 (默认行为)')
    query_group.add_argument("-k", "--apikey",
                             help="Quake API Key (优先使用 QUAKE_API_KEY 环境变量)")
    query_group.add_argument("-f", "--file", type=Path,
                             help="包含公司名称列表的文件 (每行一个)")
    query_group.add_argument("company_name", nargs='?',  # 设为可选
                             help="要查询的单个公司名称 (如果未使用 -f)")

    # 添加缓存汇总相关的参数
    summary_group = parser.add_argument_group('缓存汇总选项')
    summary_group.add_argument("-s", "--summarize", action="store_true",
                               help="解析并汇总打印当前的缓存文件内容，不执行 API 查询。")
    summary_group.add_argument("--search", metavar='TERM',
                               help="在缓存中搜索公司名称或域名，不执行API查询")

    # 添加通用配置参数组
    config_group = parser.add_argument_group('配置选项')
    config_group.add_argument("--cache-file", type=Path, default=CACHE_FILE,
                              help="指定缓存文件路径")
    config_group.add_argument("--batch-size", type=int, default=ITERATION_BATCH_SIZE,
                              help="每次迭代查询的记录数")
    config_group.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS,
                              help="最大迭代次数")
    config_group.add_argument("--delay", type=float, default=ITERATION_DELAY,
                              help="每次迭代请求间的延时(秒)")
    config_group.add_argument("--retry-delay", type=float, default=RETRY_DELAY,
                              help="遇到速率限制时的重试延时(秒)")

    # 解析命令行参数
    args = parser.parse_args()

    # --- 更新全局配置变量 ---
    CACHE_FILE = args.cache_file
    ITERATION_BATCH_SIZE = args.batch_size
    MAX_ITERATIONS = args.max_iterations
    ITERATION_DELAY = args.delay
    RETRY_DELAY = args.retry_delay

    # --- 模式判断：是汇总缓存还是执行查询？ ---
    if args.search:
        search_cache(args.search)
        sys.exit(0)  # 完成搜索后退出
    if args.summarize:
        # 如果指定了 -s/--summarize，执行汇总并退出
        summarize_cache_file()
        sys.exit(0)  # 正常退出

    # --- 如果不是汇总模式，则执行查询逻辑 ---

    # --- 决定使用的 API Key ---
    api_key_to_use = API_KEY_ENV
    if args.apikey:
        api_key_to_use = args.apikey
        print("[信息] 使用命令行提供的 API Key。")
    if not api_key_to_use:
        # 只有在执行查询时才需要 API Key
        parser.error("未找到 API Key。请设置 QUAKE_API_KEY 环境变量或使用 -k 参数。")

    # --- 决定要查询的公司列表 ---
    companies_to_query = []
    # 检查查询参数是否有效
    if args.file and args.company_name:
        parser.error("参数错误: 不能同时使用 -f 文件和指定单个公司名称进行查询。")
    elif args.file:
        if not args.file.is_file():
            parser.error(f"文件未找到: {args.file}")
        print(f"[*] 从文件读取公司列表: {args.file}")
        try:
            lines = args.file.read_text(encoding='utf-8').splitlines()
            companies_to_query = [line.strip() for line in lines if line.strip()]
            if not companies_to_query:
                parser.error(f"文件 '{args.file}' 为空或不包含有效公司名称。")
            print(f"[*] 文件中找到 {len(companies_to_query)} 个公司名称。")
        except Exception as e:
            parser.error(f"读取文件 '{args.file}' 时出错: {e}")
    elif args.company_name:
        companies_to_query = [args.company_name.strip()]
        if not companies_to_query[0]:
            parser.error("提供的公司名称无效。")
    else:
        # 如果没有指定 -s，则必须提供查询目标
        parser.error("必须提供一个公司名称、或使用 -f 指定一个文件、或使用 -s 汇总缓存。")

    # --- 循环处理查询列表中的每个公司 ---
    all_results = {}
    errors_occurred = False

    for company in companies_to_query:
        icp_objects_list = get_company_icp_info_cached_iterative(api_key_to_use, company)
        all_results[company] = icp_objects_list
        if icp_objects_list is None:
            errors_occurred = True
        print("-" * (22 + len(f" 完成查询: {company} ")))

    # --- 查询结束，汇总并打印本次运行的结果 ---
    print("\n" + "=" * 20 + " 本次运行查询结果汇总 " + "=" * 20)
    success_count = 0
    fail_count = 0
    for company, icp_list in all_results.items():
        print(f"\n--- 公司: {company} ---")
        if icp_list is not None:
            success_count += 1
            if icp_list:
                print(f"[*] 查询成功，共找到 {len(icp_list)} 条唯一域名的 ICP 记录 (主体精确匹配，按备案号升序):")
                sorted_icp_list = sorted(icp_list, key=lambda x: x.get('licence', ''))
                for icp_info in sorted_icp_list:
                    print(f"  - 域名: {icp_info.get('domain', 'N/A')}, 备案号: {icp_info.get('licence', 'N/A')}")
            else:
                print("[*] 查询成功，但未找到主体精确匹配的备案域名及ICP信息。")
        else:
            fail_count += 1
            print("[!] 查询失败或中途终止，请检查上面的错误和调试信息。")

    print("\n" + "=" * 20 + " 本次运行查询统计 " + "=" * 20)
    print(f"总查询公司数: {len(companies_to_query)}")
    print(f"成功完成查询: {success_count}")
    print(f"查询失败/终止: {fail_count}")
    print("=" * (44 + len(" 本次运行查询统计 ")))

    # 如果在任何公司的查询过程中发生错误，脚本以非零状态码退出
    if errors_occurred:
        sys.exit(1)
