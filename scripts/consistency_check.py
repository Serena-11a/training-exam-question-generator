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

支持的题目格式（选项部分）:
    - 当前标准（题目首行+选项逐行，无前缀）：【题型】题干（A） / 选项文字一行 / 选项文字二行 / 解析：…… / 难易度：
      每个选项单独一行，不带 A./B./C. 序号前缀，直接写选项文字
    - 旧式（多行选项带 A./B. 前缀）：选项逐行，可带 A./B. 前缀（脚本会自动剥离前缀便于比对）
    - 紧凑式（单行）：【单选题】题干（A）opt1 opt2 opt3 opt4 解析：…… 难易度： 分数：
      选项空格分隔、与题目同行，位于答案括号与"解析："之间
    - 题干单行+字段分行式：【题型】题干（A）opt1 opt2 ……  /  解析：……  /  难易度：  /  分数：
      选项与题目同行，解析/难易度/分数各占一行
填空题特殊：填空N：答案|备选 单独一行（像选项），并额外带 分数 行（无 考核点）。
简答题特殊：用 正确答案： 代替 解析：，无解析行，带 分数 行。

检查项:
    ▲ 格式合规（结构层，先于内容检查）：
       - 填空题 填空N 须单独成行（不可挤在题干同行）、且须含 解析/难易度/分数、不可含 考核点
       - 简答题 须用「正确答案」且不可含「解析」、须含 难易度/分数、不可含 考核点
       - 单选/多选/判断 不可含 分数/考核点、须含 解析/难易度
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


def collect_options(block, tail='', qtype=''):
    """收集选项文字与解析文字。

    支持的格式：
      - 当前标准（题目首行+选项逐行，无 A./B. 前缀）：选项各行直接写文字，位于题干行与解析行之间
      - 旧式（多行选项带 A./B. 前缀）：选项各占一行带编号，脚本自动剥离行首前缀
      - 紧凑式（单行）/ 分行式：选项与题目同行，位于「答案括号」与「解析：」之间
      - 填空/判断/简答：无选项行
    选项文字会统一剥去行首的 "A. " / "B. " 等编号前缀，便于一致性比对。
    """
    opts = []
    expl = ''
    # —— 同行选项（兼容旧紧凑/分行格式）——
    if qtype in ('单选题', '多选题'):
        m = re.search(r'[）)]\s*(.*)', tail)
        if m:
            seg = m.group(1).strip()
            mj = re.search(r'解析[:：]', seg)
            if mj:
                seg = seg[:mj.start()].strip()
            if seg and not seg.startswith('填空') \
                    and not seg.startswith(('解析', '难易度', '分数', '考核点')):
                opts = [x for x in re.split(r'\s+', seg)
                        if x and not x.startswith(('解析', '难易度', '分数', '考核点', '填空'))]
    # —— 多行部分（当前标准：选项逐行，无前缀）——
    for l in block[1:]:
        ls = l.strip()
        if ls.startswith('解析'):
            expl = ls.split('：', 1)[1].strip() if '：' in ls else ls[2:].strip()
            continue
        if ls.startswith(('难易度', '分数', '考核点', '填空', '【')):
            continue
        if ls and qtype in ('单选题', '多选题'):
            # 剥去行首编号前缀：A. B. C. 或 A． A、 等（兼容旧格式）
            ls2 = re.sub(r'^[A-Za-z][.．、]\s*', '', ls)
            opts.append(ls2)
    # —— 解析文字（紧凑式常在 tail 末尾）——
    if not expl:
        me = re.search(r'解析[:：](.*?)(?:难易度[:：]|$)', tail)
        if me:
            expl = me.group(1).strip()
    return opts, expl


def extract_fill_answers(tail, block=None):
    """从填空题提取 填空N：答案|备选 的主答案（| 之前部分）。
    兼容两种格式：
      - 旧式：填空N 挤在题干同行 tail 中
      - 新式：填空N 单独一行，在 block 行列表中
    """
    ans = []
    # 先从 tail（题干行）中提取
    for m in re.finditer(r'填空\d+[：:]\s*([^ 填空]+?)(?:\s*(?:填空\d)|$)', tail):
        primary = m.group(1).split('|')[0].strip()
        if primary:
            ans.append(primary)
    # 再从 block 行中提取（新格式：填空N 单独一行）
    if block:
        for l in block[1:]:
            ls = l.strip()
            m = re.match(r'^填空\d+[：:]\s*(.+)$', ls)
            if m:
                primary = m.group(1).split('|')[0].strip()
                if primary:
                    ans.append(primary)
    return ans


def letter_map(options):
    return {chr(ord('A') + idx): opt for idx, opt in enumerate(options)}


def _has_field(block, prefix):
    """block 中是否存在以 prefix 开头的字段行（如 '解析' / '分数' / '考核点'）。"""
    for l in block:
        if l.strip().startswith(prefix):
            return True
    return False


def format_compliance(q):
    """格式合规检查（独立于内容一致性），确保五类题型结构正确、不会因格式跑偏而出错。
    能拦住：填空挤在题干同行、多出/缺少 考核点、简答误用 解析、填空题缺 分数、简答题缺 正确答案 等。
    """
    issues = []
    qtype = q['qtype']
    block = q.get('block', [])
    has_jiexi = _has_field(block, '解析')
    has_zhengque = _has_field(block, '正确答案')
    has_nandu = _has_field(block, '难易度')
    has_fenshu = _has_field(block, '分数')
    has_kaohe = _has_field(block, '考核点')
    has_kong = any(re.match(r'^填空\d+[：:]', l.strip()) for l in block)

    if qtype in ('单选题', '多选题', '判断题'):
        if has_fenshu:
            issues.append('题型 %s 不应含「分数」行' % qtype)
        if has_kaohe:
            issues.append('题型 %s 不应含「考核点」行' % qtype)
        if not has_jiexi and not has_zhengque:
            issues.append('缺少「解析」行')
        if not has_nandu:
            issues.append('缺少「难易度」行')
    elif qtype == '填空题':
        if not has_kong:
            issues.append('填空题缺少「填空N」行（须每个单独一行，不可挤在题干同行）')
        if not has_jiexi:
            issues.append('填空题缺少「解析」行')
        if not has_nandu:
            issues.append('填空题缺少「难易度」行')
        if not has_fenshu:
            issues.append('填空题缺少「分数」行')
        if has_kaohe:
            issues.append('填空题不应含「考核点」行')
        if has_zhengque:
            issues.append('填空题不应使用「正确答案」（应为「解析」）')
    elif qtype == '简答题':
        if not has_zhengque:
            issues.append('简答题缺少「正确答案」行（不能用「解析」代替）')
        if has_jiexi:
            issues.append('简答题不应含「解析」行（用「正确答案」）')
        if not has_nandu:
            issues.append('简答题缺少「难易度」行')
        if not has_fenshu:
            issues.append('简答题缺少「分数」行')
        if has_kaohe:
            issues.append('简答题不应含「考核点」行')
    return issues


def split_items(s):
    return [x.strip() for x in re.split(r'[、,，;；]', s) if x.strip()]


def check(q):
    issues = format_compliance(q)  # 先跑格式合规检查，拦住结构错误
    qtype = q['qtype']
    if qtype == '填空题':
        fills = extract_fill_answers(q['tail'], q.get('block'))
        expl = ''
        for l in q['block'][1:]:
            ls = l.strip()
            if ls.startswith('解析'):
                expl = ls.split('：', 1)[1].strip() if '：' in ls else ls[2:].strip()
        if fills and expl:
            for fa in fills:
                if fa not in expl:
                    issues.append('填空答案「%s」未在解析中出现，请核对' % fa[:30])
        return issues
    if qtype == '判断题':
        return issues  # 判断题无选项，仅做格式层面人工核对
    if qtype not in ('单选题', '多选题'):
        return issues  # 简答题等暂不做一致性比对
    ans_letters, _ = extract_answer(qtype, q['tail'])
    if not ans_letters:
        issues.append('未识别到答案字母')
        return issues
    opts, expl = collect_options(q['block'], q['tail'], qtype)
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
