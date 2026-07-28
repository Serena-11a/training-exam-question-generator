#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consistency_check.py — 题库答案/选项/解析一致性校验

用法:
    python3 consistency_check.py <题库文件1> [题库文件2 ...] [--report 报告路径.txt]

功能:
    1. 解析每道单选题/多选题/判断题
    2. 提取标注答案字母/正误，映射到选项文字
    3. 提取"解析："文字，做一致性启发式检查
    4. 输出疑似矛盾报告（含文件名、行号、题目、标注答案、诊断）

支持三种题目格式:
    - 旧式（多行选项）：选项逐行，可带/不带 A./B. 前缀
    - 紧凑式（单行）：【单选题】题干（A）opt1 opt2 opt3 opt4 解析：…… 难易度： 分数：
      选项空格分隔、与题目同行，位于答案括号与"解析："之间
    - 题干单行+字段分行式：【题型】题干（A）opt1 opt2 ……  /  解析：……  /  难易度：  /  分数：
      选项与题目同行，解析/难易度/分数各占一行

检查项:
    A. 答案字母越界（指向不存在的选项）
    B. 排除题("不包括/不属于/不是/错误的是")：答案选项不应出现在解析正向陈述中
    C. 非排除题：若解析中完整出现某"非答案"选项内容、而"答案"选项内容未出现 → 标记"答案与解析矛盾"
    D. 数字一致性：解析含数值但该数值不在任何选项中
仅使用标准库，可在隔离 python 环境直接运行。
"""
import re
import sys
import os


def parse_questions(lines):
    """解析题库，返回题目块列表"""
    questions = []
    i = 0
    n = len(lines)
    qnum = 0
    while i < n:
        line = lines[i].strip()
        m = re.match(r'^【(单选题|多选题|判断题|填空题|简答题)】(.*)', line)
        if not m:
            i += 1
            continue
        qtype = m.group(1)
        qtail = m.group(2)
        qnum += 1
        block = [line]
        j = i + 1
        while j < n:
            l = lines[j].strip()
            if l.startswith('【') and re.match(r'^【(单选|多选|判断|填空|简答)题】', l):
                break
            if l.startswith('====') and set(l) == {'='}:
                break
            block.append(l)
            j += 1
        questions.append({
            'qnum': qnum,
            'qtype': qtype,
            'tail': qtail,
            'block': block,
            'line_no': i + 1,
        })
        i = j
    return questions


def extract_answer(qtype, tail):
    if qtype in ('单选题', '多选题'):
        m = re.search(r'[（(]\s*([A-Za-z]+)\s*[)）]', tail)
        return (m.group(1).upper() if m else None), None
    if qtype == '判断题':
        m = re.search(r'[（(]\s*(正确|错误)\s*[)）]', tail)
        return None, (m.group(1) if m else None)
    return None, None


def collect_options(block, tail=''):
    """收集选项文字与解析文字。

    支持三种格式：
      - 旧式（多行选项）：选项逐行（无前缀或 A./B. 前缀）
      - 紧凑式（单行）：选项空格分隔、与题目同行，位于「答案括号」与「解析：」之间
      - 题干单行+字段分行式：选项与题目同行，「解析：/难易度：/分数：」各占一行
    """
    opts = []
    expl = ''
    # —— 选项在「答案括号」之后 ——
    # 紧凑式：同行含 解析，截断到 解析 之前；分行式：该行只有「题干+选项」，整段即选项
    m = re.search(r'[）)]\s*(.*)', tail)
    if m:
        seg = m.group(1).strip()
        mj = re.search(r'解析[:：]', seg)
        if mj:
            seg = seg[:mj.start()].strip()
        if seg:
            opts = [x for x in re.split(r'\s+', seg) if x]
    # —— 多行部分：解析/难易度/分数/考核点/填空 跳过，其余按旧式选项 ——
    for l in block[1:]:
        ls = l.strip()
        if ls.startswith('解析'):
            expl = ls.split('：', 1)[1].strip() if '：' in ls else ls[2:].strip()
            continue
        if ls.startswith(('难易度', '分数', '考核点', '填空')):
            continue
        if ls:
            opts.append(ls)
    # —— 解析文字（紧凑式常在 tail 末尾）——
    if not expl:
        me = re.search(r'解析[:：](.*?)(?:难易度[:：]|$)', tail)
        if me:
            expl = me.group(1).strip()
    return opts, expl


def letter_map(options):
    return {chr(ord('A') + idx): opt for idx, opt in enumerate(options)}


def split_items(s):
    return [x.strip() for x in re.split(r'[、,，;；]', s) if x.strip()]


def check(q):
    issues = []
    qtype = q['qtype']
    if qtype not in ('单选题', '多选题'):
        return issues  # 判断题/填空/简答此处仅做基础解析检查（可扩展）
    ans_letters, _ = extract_answer(qtype, q['tail'])
    if not ans_letters:
        issues.append('未识别到答案字母')
        return issues
    opts, expl = collect_options(q['block'], q['tail'])
    lmap = letter_map(opts)
    if any(ch not in lmap for ch in ans_letters):
        issues.append('答案字母 %s 超出选项范围 (实际选项: %s)'
                      % (ans_letters, list(lmap.keys())))
        return issues
    ans_opts = [lmap[ch] for ch in ans_letters]
    ans_text = ' '.join(ans_opts)

    is_excl = any(k in q['tail'] for k in
                  ('不包括', '不属于', '不是', '不含有', '错误的是', '不正确的是'))
    if not expl:
        return issues

    if is_excl:
        # 排除题：答案选项不应出现在解析"正向"陈述里。
        # 但若答案出现在"不包括X/不属于X/不是X"的否定语境，属正常（答案即被排除项），不报错。
        ans_in_expl = any(opt in expl for opt in ans_opts if len(opt) > 2)
        if ans_in_expl:
            negated = False
            for opt in ans_opts:
                if len(opt) > 2 and re.search(
                        r'(?:不包括|不属于|不是|不含有|不含|没有|无)[^，。、；]{0,10}?%s'
                        % re.escape(opt), expl):
                    negated = True
                    break
            if not negated:
                issues.append('排除题但答案(%s:%s)出现在解析中，疑似答案错误'
                              % (ans_letters, ans_text[:30]))
    else:
        # 非排除题：检查解析是否完整出现某非答案选项，且答案选项未在解析出现
        for ch, opt in lmap.items():
            if ch in ans_letters or len(opt) < 3:
                continue
            if opt in expl:
                ans_present = any(
                    (lmap.get(a) in expl) or
                    any(it in expl for it in split_items(lmap.get(a, '')))
                    for a in ans_letters
                )
                if not ans_present:
                    issues.append('解析中完整出现非答案选项 %s(%s)，但答案 %s 未在解析出现，疑似答案标错'
                                  % (ch, opt[:30], ans_letters))
                    break
        # 数字一致性：解析含数值但该数值不在任何选项中
        nums_expl = set(re.findall(r'\d+(?:\.\d+)?', expl))
        if nums_expl:
            all_opt_nums = set()
            for o in opts:
                all_opt_nums |= set(re.findall(r'\d+(?:\.\d+)?', o))
            missing = nums_expl - all_opt_nums
            if missing:
                issues.append('解析含数值 %s 但不在任何选项文字中，请核对'
                              % sorted(missing))
    return issues


def main():
    files = []
    report = None
    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == '--report':
            i += 1
            if i < len(sys.argv):
                report = sys.argv[i]
        elif a.startswith('--report='):
            report = a.split('=', 1)[1]
        else:
            files.append(a)
        i += 1

    if not files:
        print('用法: python3 consistency_check.py <题库文件> [--report out.txt]')
        sys.exit(1)

    all_issues = []
    for f in files:
        if not os.path.exists(f):
            print('[跳过] 文件不存在: %s' % f)
            continue
        with open(f, 'r', encoding='utf-8') as fh:
            lines = fh.readlines()
        qs = parse_questions(lines)
        cnt = 0
        for q in qs:
            iss = check(q)
            if iss:
                cnt += 1
                all_issues.append((f, q, iss))
        print('文件 %s: 解析 %d 题, 疑似问题 %d 题'
              % (os.path.basename(f), len(qs), cnt))

    out_lines = []
    for f, q, iss in all_issues:
        out_lines.append('文件: %s  行号: %d  类型: %s'
                         % (os.path.basename(f), q['line_no'], q['qtype']))
        out_lines.append('  题目: %s' % q['tail'][:70])
        if q['qtype'] in ('单选题', '多选题'):
            ans, _ = extract_answer(q['qtype'], q['tail'])
            out_lines.append('  标注答案: %s' % ans)
        for it in iss:
            out_lines.append('  ⚠️ %s' % it)
        out_lines.append('')
    report_text = '\n'.join(out_lines)
    if report:
        with open(report, 'w', encoding='utf-8') as fh:
            fh.write(report_text if report_text else '未发现一致性问题\n')
        print('报告已写入: %s' % report)
    else:
        print('\n' + (report_text if report_text else '未发现一致性问题'))


if __name__ == '__main__':
    main()
