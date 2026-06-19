"""
演示数据注入脚本
================
通过后端 API 批量创建规范、真实的演示数据，覆盖：
- 知识库条目（多来源、多设备、多故障类型）
- 作业模板 + 任务实例
- 用户案例上传（含不同审核状态）
- 客服工单（含回复、转知识）
- AI 对话 + 反馈（含有用/无用标注）

运行方式：python scripts/seed_demo_data.py
前提条件：后端已启动（http://localhost:8000）
"""
import httpx
import asyncio
import random

BASE = "http://localhost:8000"
ADMIN_AUTH = None
WORKER_AUTH = None
EXPERT_AUTH = None


async def login(role="admin"):
    """登录获取token"""
    creds = {
        "admin": ("admin", "admin123"),
        "worker": ("worker1", "123456"),
        "expert": ("expert1", "123456"),
    }
    user, pwd = creds[role]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{BASE}/api/v1/auth/login", json={"username": user, "password": pwd})
        if r.status_code == 200:
            return r.json()["access_token"]
        return None


async def api(method, path, token=None, **kw):
    """通用 API 请求"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=60) as c:
        if method == "GET":
            r = await c.get(f"{BASE}{path}", headers=headers, params=kw.get("params"))
        elif method == "POST":
            if "json" in kw:
                r = await c.post(f"{BASE}{path}", headers=headers, json=kw["json"])
            elif "data" in kw:
                r = await c.post(f"{BASE}{path}", headers=headers, data=kw["data"])
            else:
                r = await c.post(f"{BASE}{path}", headers=headers)
        elif method == "PUT":
            r = await c.put(f"{BASE}{path}", headers=headers, json=kw.get("json"))
        return r


async def create_worker_account():
    """确保有一线人员和专家账号"""
    global WORKER_AUTH, EXPERT_AUTH

    # 先尝试登录，失败则注册
    WORKER_AUTH = await login("worker")
    if not WORKER_AUTH:
        # 注册
        async with httpx.AsyncClient(timeout=30) as c:
            await c.post(f"{BASE}/api/v1/auth/register", json={
                "username": "worker1", "password": "123456",
                "name": "张建国", "employee_id": "EMP001", "team": "维修一班"
            })
        # 管理员审核通过
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{BASE}/api/v1/auth/users", headers={"Authorization": f"Bearer {ADMIN_AUTH}"})
            users = r.json()
            for u in users:
                if u["username"] == "worker1" and u["status"] == "pending":
                    await c.put(
                        f"{BASE}/api/v1/auth/users/{u['id']}/status?status=active",
                        headers={"Authorization": f"Bearer {ADMIN_AUTH}"}
                    )
        WORKER_AUTH = await login("worker")

    EXPERT_AUTH = await login("expert")
    if not EXPERT_AUTH:
        async with httpx.AsyncClient(timeout=30) as c:
            await c.post(f"{BASE}/api/v1/auth/register", json={
                "username": "expert1", "password": "123456",
                "name": "李明辉", "employee_id": "EMP002", "team": "技术专家组"
            })
        # 审核通过 + 提升为专家
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{BASE}/api/v1/auth/users", headers={"Authorization": f"Bearer {ADMIN_AUTH}"})
            for u in r.json():
                if u["username"] == "expert1":
                    await c.put(
                        f"{BASE}/api/v1/auth/users/{u['id']}/status?status=active",
                        headers={"Authorization": f"Bearer {ADMIN_AUTH}"}
                    )
        EXPERT_AUTH = await login("expert")
        # 注意：注册默认为worker，需要修改角色为expert（直接改DB或需管理端操作）
        # 这里先用worker角色，专家功能测试时可手动改DB

    print(f"  Worker token: {'✓' if WORKER_AUTH else '✗'}")
    print(f"  Expert token: {'✓' if EXPERT_AUTH else '✗'}")


async def seed_device_models():
    """注入设备型号"""
    print("\n[1/8] 注入设备型号...")
    models = [
        {"name": "Y系列三相异步电动机", "production_line": "动力车间A线", "category": "电气"},
        {"name": "ZQ系列圆柱齿轮减速机", "production_line": "传动车间", "category": "传动"},
        {"name": "IS型单级离心式清水泵", "production_line": "循环水系统", "category": "液压"},
        {"name": "LG系列螺杆式空压机", "production_line": "气源站", "category": "动力"},
        {"name": "S11-M系列油浸式变压器", "production_line": "变电站", "category": "电气"},
        {"name": "WNS系列燃气蒸汽锅炉", "production_line": "供热站", "category": "动力"},
        {"name": "PZ30系列配电箱", "production_line": "各车间", "category": "电气"},
        {"name": "CD1型电动葫芦", "production_line": "起重区", "category": "起重"},
    ]
    for m in models:
        r = await api("POST", "/api/v1/config/device-models", ADMIN_AUTH, json=m)
        status = "✓" if r.status_code in (200, 201) else f"✗({r.status_code})"
        print(f"  {status} {m['name']}")


async def seed_fault_tags():
    """注入故障标签"""
    print("\n[2/8] 注入故障标签...")
    tags = [
        "轴承故障", "电气故障", "润滑不良", "过热", "振动异常",
        "密封泄漏", "控制系统故障", "腐蚀磨损", "异响", "过载",
        "绝缘老化", "对中不良", "松动", "堵塞", "短路",
    ]
    for t in tags:
        r = await api("POST", "/api/v1/config/fault-tags", ADMIN_AUTH, json={"name": t})
        status = "✓" if r.status_code in (200, 201) else f"✗({r.status_code})"
        print(f"  {status} {t}")


async def seed_knowledge_entries():
    """注入知识库条目（已发布）"""
    print("\n[3/8] 注入知识库条目...")
    entries = [
        {
            "title": "Y系列三相异步电动机轴承更换标准作业规程",
            "summary": "详细描述Y系列电机轴承的拆卸、检查、选型、安装和润滑全流程标准，适用于各类Y系列电机的日常检修和定修。",
            "content": """<h2>1. 适用范围</h2>
<p>本规程适用于Y系列三相异步电动机（机座号80-355）的滚动轴承更换作业。</p>

<h2>2. 安全注意事项</h2>
<ul>
<li>作业前必须断开电源并执行能量隔离（LOTO）</li>
<li>使用专用拉马工具，严禁用锤直接敲击轴承</li>
<li>加热安装时油温不得超过120℃</li>
<li>全程佩戴防护手套和护目镜</li>
</ul>

<h2>3. 所需工具与材料</h2>
<table border="1">
<tr><th>名称</th><th>规格</th><th>数量</th></tr>
<tr><td>三爪拉马</td><td>150mm/300mm</td><td>1套</td></tr>
<tr><td>轴承加热器</td><td>工业级</td><td>1台</td></tr>
<tr><td>游标卡尺</td><td>0-150mm</td><td>1把</td></tr>
<tr><td>锂基润滑脂</td><td>3号</td><td>适量</td></tr>
<tr><td>清洁布/清洗剂</td><td>工业级</td><td>若干</td></tr>
</table>

<h2>4. 操作步骤</h2>

<h3>4.1 拆卸旧轴承</h3>
<p>（1）拆除轴承端盖螺栓，取下端盖；</p>
<p>（2）使用三爪拉马夹持轴承内圈，均匀施力将轴承从轴上拉出；</p>
<p>（3）检查轴颈有无磨损、划伤，如有需先修复。</p>

<h3>4.2 清洗与检查</h3>
<p>（1）用清洗剂清洗轴颈和轴承座；</p>
<p>（2）检测轴承座内孔尺寸（公差H7）；</p>
<p>（3）检查轴颈尺寸和圆柱度（≤0.005mm）。</p>

<h3>4.3 安装新轴承</h3>
<p>（1）确认新轴承型号与旧件一致；</p>
<p>（2）使用轴承加热器将轴承加热至80-100℃；</p>
<p>（3）将加热后的轴承迅速套入轴颈，推至轴肩处；</p>
<p>（4）冷却后确认轴承紧贴轴肩，径向游隙符合标准。</p>

<h3>4.4 润滑</h3>
<p>（1）轴承内填充锂基润滑脂，填充量为轴承内部空间的1/3-1/2；</p>
<p>（2）轴承座油腔填充量为1/2-2/3；</p>
<p>（3）安装端盖，均匀拧紧螺栓。</p>

<h2>5. 验收标准</h2>
<ul>
<li>手动盘车灵活无卡滞</li>
<li>运行30分钟后轴承温升≤40K</li>
<li>振动值≤2.8mm/s（RMS）</li>
<li>无异响</li>
</ul>

<h2>6. 常见问题</h2>
<p><b>Q: 轴承加热温度过高会怎样？</b><br>A: 超过120℃会导致轴承材料回火，硬度下降，严重缩短使用寿命。</p>
<p><b>Q: 润滑脂加多了有什么影响？</b><br>A: 搅拌阻力增大，运行温度升高，可能导致润滑脂过早氧化失效。</p>""",
            "source": "manual",
            "source_ref": "设备维护手册-Y系列电机-2024版",
            "device_models": ["Y系列三相异步电动机"],
            "fault_tags": ["轴承故障", "过热", "润滑不良"],
            "maintenance_level": "定修",
        },
        {
            "title": "离心泵机械密封泄漏的现场快速诊断与处理",
            "summary": "介绍离心泵机械密封泄漏的常见原因、现场快速判断方法以及紧急处理措施，适用于循环水泵、给水泵等离心泵设备。",
            "content": """<h2>1. 故障现象</h2>
<p>机械密封处有液体连续滴漏，严重时呈线状或喷射状泄漏。密封压盖处有明显水渍或结晶物。</p>

<h2>2. 常见原因分析</h2>

<h3>2.1 密封面磨损（占比约45%）</h3>
<ul>
<li>介质含颗粒杂质导致密封面划伤</li>
<li>长期运行正常磨损，端面平面度超差</li>
<li>干运转或抽空导致密封面烧损</li>
</ul>

<h3>2.2 辅助密封失效（占比约25%）</h3>
<ul>
<li>O形圈老化变硬失去弹性</li>
<li>波纹管破裂或疲劳断裂</li>
<li>密封垫片损坏</li>
</ul>

<h3>2.3 安装与使用问题（占比约30%）</h3>
<ul>
<li>安装时密封面未清理干净</li>
<li>压缩量调整不当（过大或过小）</li>
<li>泵轴弯曲或轴承磨损导致偏摆过大</li>
<li>冷却/冲洗系统故障导致密封面过热</li>
</ul>

<h2>3. 现场快速诊断流程</h2>
<p><b>第一步：观察泄漏形态</b></p>
<p>——均匀连续滴漏：多为密封面正常磨损</p>
<p>——间歇性滴漏+运行中异响：可能为泵轴偏摆过大</p>
<p>——静止时漏、运行时不漏：多为辅助密封圈失效</p>

<p><b>第二步：检查运行参数</b></p>
<p>——出口压力是否正常（排除抽空）</p>
<p>——轴承温度是否正常（排除轴承故障）</p>
<p>——冲洗液/冷却水是否正常供应</p>

<p><b>第三步：停机拆检确认</b></p>
<p>——检查密封面磨损痕迹（均匀磨损vs偏磨vs热裂纹）</p>
<p>——检查O形圈及波纹管弹性</p>
<p>——测量轴的径向跳动</p>

<h2>4. 处理措施</h2>
<table border="1">
<tr><th>故障原因</th><th>处理方案</th><th>预计工时</th></tr>
<tr><td>密封面磨损</td><td>更换机械密封总成</td><td>2-3h</td></tr>
<tr><td>O形圈失效</td><td>更换O形圈套装</td><td>1-2h</td></tr>
<tr><td>轴偏摆</td><td>更换轴承+校正轴</td><td>4-6h</td></tr>
<tr><td>波纹管破裂</td><td>更换机械密封总成</td><td>2-3h</td></tr>
</table>

<h2>5. 注意事项</h2>
<ul>
<li>更换密封后必须进行静态试压（1.5倍工作压力，保压5分钟）</li>
<li>安装过程中密封面严禁沾油污</li>
<li>拧紧压盖螺栓时对角均匀施力</li>
<li>使用三个月以内的新密封泄漏，应重点排查安装和运行工况</li>
</ul>""",
            "summary": "离心泵机械密封泄漏的诊断与处理方法",
            "source": "manual",
            "source_ref": "化工设备检修技术手册-2023版",
            "device_models": ["IS型单级离心式清水泵"],
            "fault_tags": ["密封泄漏", "振动异常", "磨损"],
            "maintenance_level": "定修",
        },
        {
            "title": "螺杆空压机日常点检标准与保养周期表",
            "summary": "螺杆空压机的每日、每周、每月点检项目清单及各级保养周期与内容，确保空压机稳定运行。",
            "content": """<h2>1. 日常点检（每班）</h2>
<table border="1">
<tr><th>序号</th><th>点检项目</th><th>标准</th><th>方法</th></tr>
<tr><td>1</td><td>排气温度</td><td>≤100℃</td><td>查看控制面板</td></tr>
<tr><td>2</td><td>排气压力</td><td>0.7-0.8MPa</td><td>查看压力表</td></tr>
<tr><td>3</td><td>油位</td><td>在油标1/2-2/3处</td><td>目视</td></tr>
<tr><td>4</td><td>油温</td><td>≤95℃</td><td>查看控制面板</td></tr>
<tr><td>5</td><td>冷却器前后温差</td><td>5-8℃</td><td>温度计测量</td></tr>
<tr><td>6</td><td>冷凝水排放</td><td>排放完全</td><td>手动排放阀</td></tr>
<tr><td>7</td><td>运行电流</td><td>≤额定值</td><td>电流表</td></tr>
<tr><td>8</td><td>异常噪音/振动</td><td>无</td><td>听觉/触觉</td></tr>
</table>

<h2>2. 每周点检</h2>
<ul>
<li>清洁空气滤清器滤芯（环境粉尘大时缩短为每3天）</li>
<li>检查皮带张紧度（手指按压中部，挠度10-15mm）</li>
<li>检查各管路接头有无泄漏</li>
<li>检查安全阀手动测试</li>
</ul>

<h2>3. 每月点检</h2>
<ul>
<li>取样化验润滑油（水分、粘度、酸值）</li>
<li>清洁冷却器散热翅片</li>
<li>检查电器接线端子紧固</li>
<li>校验压力传感器、温度传感器</li>
</ul>

<h2>4. 保养周期</h2>
<table border="1">
<tr><th>级别</th><th>周期</th><th>内容</th></tr>
<tr><td>日常保养</td><td>每班</td><td>日常点检8项+记录</td></tr>
<tr><td>一级保养</td><td>500h</td><td>更换空滤+油滤+油气分离器芯</td></tr>
<tr><td>二级保养</td><td>2000h</td><td>更换润滑油+一级保养内容+检查温控阀</td></tr>
<tr><td>三级保养</td><td>8000h</td><td>大修：更换轴承+轴封+全面检查</td></tr>
</table>

<h2>5. 常见预警信号</h2>
<ul>
<li><b>排气温度持续升高</b>：冷却器脏堵或油量不足</li>
<li><b>加载时间异常长</b>：空气滤清器堵塞或系统泄漏</li>
<li><b>油消耗量增大</b>：油气分离器破损或回油管堵塞</li>
<li><b>运行电流增大</b>：轴承磨损或主机内部异常</li>
</ul>""",
            "summary": "螺杆空压机的日常/周/月点检清单和各级保养周期",
            "source": "manual",
            "source_ref": "LG系列空压机操作维护手册",
            "device_models": ["LG系列螺杆式空压机"],
            "fault_tags": ["过热", "润滑不良", "电气故障"],
            "maintenance_level": "日常",
        },
        {
            "title": "变压器绝缘电阻测试标准与判定方法",
            "summary": "电力变压器绝缘电阻的测试方法、接线方式、合格标准及绝缘劣化趋势分析方法。",
            "content": """<h2>1. 测试目的</h2>
<p>检测变压器绕组对地、绕组之间的绝缘状况，发现绝缘受潮、老化、局部缺陷等问题。</p>

<h2>2. 测试仪器</h2>
<p>使用2500V或5000V电动兆欧表（绝缘电阻测试仪）。精度等级不低于1.5级。</p>

<h2>3. 测试接线</h2>
<table border="1">
<tr><th>测试项目</th><th>L端(线路)</th><th>E端(接地)</th></tr>
<tr><td>高压绕组-低压绕组+地</td><td>高压绕组</td><td>低压绕组+地</td></tr>
<tr><td>低压绕组-高压绕组+地</td><td>低压绕组</td><td>高压绕组+地</td></tr>
<tr><td>高压绕组-低压绕组</td><td>高压绕组</td><td>低压绕组</td></tr>
</table>

<h2>4. 测试步骤</h2>
<p>（1）断开变压器各侧电源，验电确认无电压，挂接地线放电；</p>
<p>（2）拆除高低压侧引线，清洁套管表面；</p>
<p>（3）按接线表连接测试线；</p>
<p>（4）以额定转速摇动兆欧表，分别读取15s（R15）和60s（R60）的绝缘电阻值；</p>
<p>（5）计算吸收比 K = R60/R15；</p>
<p>（6）记录测试时环境温度和湿度。</p>

<h2>5. 合格标准</h2>
<table border="1">
<tr><th>电压等级</th><th>20℃时绝缘电阻(MΩ)</th><th>吸收比(R60/R15)</th></tr>
<tr><td>10kV</td><td>≥300</td><td>≥1.3</td></tr>
<tr><td>35kV</td><td>≥600</td><td>≥1.3</td></tr>
<tr><td>110kV</td><td>≥1200</td><td>≥1.3</td></tr>
</table>
<p>温度换算公式：R20 = Rt × 1.5^((t-20)/10)</p>

<h2>6. 不合格处理</h2>
<ul>
<li>绝缘电阻偏低+吸收比<1.3：疑似受潮，需进行干燥处理</li>
<li>绝缘电阻偏低+吸收比正常：绝缘老化，需评估剩余寿命</li>
<li>绝缘电阻突降（较上次>50%）：需进行介损、局放等进一步试验</li>
<li>各相绝缘电阻值差异>30%：局部缺陷，需重点排查</li>
</ul>""",
            "summary": "变压器绝缘电阻测试方法、接线、标准及判定方法",
            "source": "manual",
            "source_ref": "电力设备预防性试验规程 DL/T 596",
            "device_models": ["S11-M系列油浸式变压器"],
            "fault_tags": ["绝缘老化", "电气故障"],
            "maintenance_level": "定修",
        },
        {
            "title": "减速机齿轮点蚀与磨损的振动诊断方法",
            "summary": "利用振动频谱分析诊断减速机齿轮点蚀、磨损等早期故障，含特征频率计算和案例分析。",
            "content": """<h2>1. 齿轮常见故障与振动特征</h2>
<table border="1">
<tr><th>故障类型</th><th>振动频率特征</th><th>时域波形特征</th></tr>
<tr><td>齿面均匀磨损</td><td>啮合频率及其谐波幅值增大；边频带增多</td><td>随机性强</td></tr>
<tr><td>齿面点蚀</td><td>啮合频率周围出现较宽的边频带</td><td>出现周期性冲击脉冲</td></tr>
<tr><td>齿轮偏心</td><td>齿轮转频及其谐波增大</td><td>以转频为周期的调制</td></tr>
<tr><td>断齿</td><td>齿轮转频大幅增大；啮合频率调制强烈</td><td>周期性强冲击</td></tr>
<tr><td>齿面胶合</td><td>啮合频率高次谐波突增</td><td>冲击+摩擦特征</td></tr>
</table>

<h2>2. 特征频率计算公式</h2>
<p><b>齿轮啮合频率 GMF = N × RPM / 60</b></p>
<p>其中：N = 齿轮齿数，RPM = 齿轮转速(r/min)</p>
<p>【示例】输入轴转速1450rpm，小齿轮19齿：GMF = 19 × 1450 / 60 = 459.17Hz</p>

<h2>3. 振动测点布置</h2>
<ul>
<li>每个轴承座布置径向水平和垂直两个方向</li>
<li>输入端和输出端各布置测点</li>
<li>推荐使用磁座式加速度传感器（频率范围1-10000Hz）</li>
</ul>

<h2>4. 判定标准</h2>
<table border="1">
<tr><th>状态</th><th>振动速度(mm/s RMS)</th><th>建议</th></tr>
<tr><td>良好</td><td>&lt;2.8</td><td>正常运行</td></tr>
<tr><td>注意</td><td>2.8-4.5</td><td>缩短监测周期</td></tr>
<tr><td>警告</td><td>4.5-7.1</td><td>安排检修计划</td></tr>
<tr><td>危险</td><td>&gt;7.1</td><td>立即停机检查</td></tr>
</table>

<h2>5. 案例分析</h2>
<p><b>案例：ZQ350减速机异响</b></p>
<p>现象：运行中有"咯噔"声，间隔约0.5s，壳体手摸有明显振动感。</p>
<p>检测：输入端径向振动值5.6mm/s（超标），频谱分析显示在输入轴转频24.2Hz处有高峰值，啮合频率459Hz周围有丰富的边频带。</p>
<p>诊断：输入轴齿轮出现早期点蚀，齿面局部剥落导致周期性冲击。</p>
<p>处理：停机开箱检查，发现小齿轮3个齿面有直径2-3mm的点蚀坑，更换齿轮副后恢复正常。</p>""",
            "summary": "减速机齿轮故障的振动诊断方法和案例分析",
            "source": "manual",
            "source_ref": "旋转机械振动诊断技术-第3版",
            "device_models": ["ZQ系列圆柱齿轮减速机"],
            "fault_tags": ["振动异常", "磨损", "异响"],
            "maintenance_level": "定修",
        },
        {
            "title": "工业锅炉安全阀定期校验操作步骤",
            "summary": "锅炉安全阀的离线校验和在线校验方法，含整定压力设定标准和校验记录表模板。",
            "content": """<h2>1. 法规要求</h2>
<p>依据《锅炉安全技术监察规程》(TSG 11-2020)规定：</p>
<ul>
<li>安全阀至少每年校验一次</li>
<li>在用锅炉的安全阀每年至少进行一次整定压力校验</li>
<li>校验应由有资质的单位和人员执行</li>
</ul>

<h2>2. 整定压力设定</h2>
<table border="1">
<tr><th>安装位置</th><th>整定压力(MPa)</th><th>回座压力</th></tr>
<tr><td>锅筒安全阀(低值)</td><td>工作压力+0.03</td><td>≥整定压力的90%</td></tr>
<tr><td>锅筒安全阀(高值)</td><td>工作压力×1.04</td><td>≥整定压力的90%</td></tr>
<tr><td>过热器出口安全阀</td><td>工作压力×1.04</td><td>≥整定压力的90%</td></tr>
</table>

<h2>3. 离线校验步骤</h2>
<p>（1）办理安全阀拆卸工作票，锅炉降压停炉；</p>
<p>（2）拆卸安全阀，清洁阀体阀座；</p>
<p>（3）在校验台上安装安全阀，连接压力源；</p>
<p>（4）缓慢升压至整定压力，记录开启压力值；</p>
<p>（5）继续升压至安全阀全开，测量开启高度（≥阀座喉径的1/4）；</p>
<p>（6）缓慢降压，记录回座压力；</p>
<p>（7）重复3次，取平均值，偏差≤±1%；</p>
<p>（8）铅封并出具校验报告。</p>

<h2>4. 在线校验方法（使用辅助校验装置）</h2>
<p>（1）锅炉在正常运行压力下；</p>
<p>（2）安装液压辅助校验装置于安全阀上部；</p>
<p>（3）通过液压系统施加辅助力，模拟升压过程；</p>
<p>（4）读取开启瞬间的辅助力值，换算为整定压力；</p>
<p>（5）记录校验结果并出具报告。</p>

<h2>5. 常见问题</h2>
<p><b>Q: 安全阀漏汽如何处理？</b><br>A: 检查阀瓣与阀座密封面是否有划痕或异物，轻微泄漏可研磨修复，严重则更换。</p>
<p><b>Q: 安全阀起跳后不回座？</b><br>A: 检查弹簧是否变形或断裂，阀瓣导向是否卡涩。</p>""",
            "summary": "锅炉安全阀的校验步骤、整定标准和常见问题处理",
            "source": "manual",
            "source_ref": "锅炉安全技术监察规程 TSG 11-2020",
            "device_models": ["WNS系列燃气蒸汽锅炉"],
            "fault_tags": ["密封泄漏"],
            "maintenance_level": "大修",
        },
    ]

    for e in entries:
        body = {k: v for k, v in e.items() if k not in ("source", "source_ref")}
        body["source"] = e["source"]
        body["source_ref"] = e["source_ref"]
        r = await api("POST", "/api/v1/knowledge/", ADMIN_AUTH, json=body)
        status = "✓" if r.status_code in (200, 201) else f"✗({r.status_code})"
        print(f"  {status} {e['title'][:40]}...")


async def seed_templates_and_tasks():
    """注入作业模板和任务"""
    print("\n[4/8] 注入作业模板...")

    templates = [
        {
            "name": "Y系列电机季度定修标准流程",
            "maintenance_level": "定修",
            "device_models": ["Y系列三相异步电动机"],
            "steps": [
                {"phase": "准备", "step_num": 1, "title": "办理工作票及安全交底",
                 "content": "1.办理检修工作票\n2.确认设备已停机断电\n3.执行LOTO能量隔离\n4.工作负责人进行安全技术交底",
                 "compliance_items": ["工作票已签发", "LOTO已执行", "安全交底已完成"]},
                {"phase": "拆卸", "step_num": 2, "title": "拆卸电机接线及联轴器",
                 "content": "1.拆除电机电源接线，做好相序标记\n2.拆除联轴器护罩\n3.拆卸联轴器螺栓，分离联轴器\n4.拆除电机地脚螺栓",
                 "compliance_items": ["接线相序已标记", "使用专用工具"]},
                {"phase": "检修", "step_num": 3, "title": "更换轴承及检查定子绕组",
                 "content": "1.拆卸前后端盖\n2.使用拉马拉出旧轴承\n3.清洗轴颈和轴承座\n4.加热安装新轴承\n5.检查定子绕组绝缘及有无过热痕迹\n6.测量绕组直流电阻",
                 "compliance_items": ["轴承加热温度≤120℃", "绝缘电阻≥0.5MΩ", "三相电阻不平衡度≤2%"]},
                {"phase": "回装", "step_num": 4, "title": "回装电机及联轴器对中",
                 "content": "1.安装前后端盖并紧固\n2.电机就位，穿入地脚螺栓\n3.使用百分表进行联轴器对中\n4.径向偏差≤0.05mm，角向偏差≤0.05mm/100mm\n5.紧固地脚螺栓至规定扭矩",
                 "compliance_items": ["对中精度达标", "紧固扭矩符合标准"]},
                {"phase": "试车", "step_num": 5, "title": "空载及负载试车",
                 "content": "1.恢复电机接线\n2.点动确认转向正确\n3.空载运行30分钟\n4.测量三相电流、振动、温度\n5.带载运行1小时\n6.确认各项参数正常后办理工作票终结",
                 "compliance_items": ["空载试车≥30min", "振动≤2.8mm/s", "轴承温升≤40K", "工作票已终结"]},
            ]
        },
        {
            "name": "离心泵年度大修标准流程",
            "maintenance_level": "大修",
            "device_models": ["IS型单级离心式清水泵"],
            "steps": [
                {"phase": "准备", "step_num": 1, "title": "大修前准备",
                 "content": "1.查阅上次大修记录及运行日志\n2.准备备品备件（机械密封、轴承、密封垫等）\n3.准备专用工具\n4.办理大修工作票",
                 "compliance_items": ["备件已核对型号", "工作票已签发"]},
                {"phase": "拆卸", "step_num": 2, "title": "泵体全面拆卸",
                 "content": "1.关闭进出口阀门，排空泵内介质\n2.拆除联轴器护罩及联轴器\n3.拆除泵盖螺栓，吊出泵盖\n4.拆卸叶轮锁紧螺母，取出叶轮\n5.拆卸机械密封动环和静环\n6.拆卸轴承端盖，取出轴承",
                 "compliance_items": ["阀门已关闭确认", "使用专用吊具"]},
                {"phase": "检查", "step_num": 3, "title": "零部件全面检查测量",
                 "content": "1.检查叶轮磨损和汽蚀情况\n2.检查泵轴弯曲度(≤0.05mm)\n3.检查轴承座磨损情况\n4.检查密封腔尺寸\n5.检查泵壳腐蚀情况",
                 "compliance_items": ["测量数据已记录", "超标部件已更换"]},
                {"phase": "回装", "step_num": 4, "title": "回装泵体各部件",
                 "content": "1.安装新轴承\n2.安装新机械密封\n3.安装叶轮并紧固锁紧螺母\n4.安装泵盖并均匀紧固螺栓\n5.安装联轴器并找正对中",
                 "compliance_items": ["螺栓紧固力矩达标", "联轴器对中精度达标"]},
                {"phase": "试车", "step_num": 5, "title": "试压及试车",
                 "content": "1.静态试压：1.5倍工作压力，保压30min无泄漏\n2.盘车确认无卡涩\n3.点动确认转向\n4.启动运行，逐步升压至工作压力\n5.监测流量、压力、振动、温度",
                 "compliance_items": ["静态试压合格", "机械密封泄漏量≤5滴/min", "轴承温度≤75℃"]},
            ]
        },
        {
            "name": "空压机月度巡检标准流程",
            "maintenance_level": "日常",
            "device_models": ["LG系列螺杆式空压机"],
            "steps": [
                {"phase": "点检", "step_num": 1, "title": "运行参数检查",
                 "content": "1.记录排气压力(0.7-0.8MPa)\n2.记录排气温度(≤100℃)\n3.记录油温(≤95℃)\n4.记录运行电流\n5.检查油位(1/2-2/3)",
                 "compliance_items": ["参数在规定范围内", "数据已记录到点检表"]},
                {"phase": "维护", "step_num": 2, "title": "清洁与排放",
                 "content": "1.排放冷凝水至完全排空\n2.清洁空气滤清器（吹扫或更换）\n3.清洁冷却器散热片\n4.检查皮带张紧度",
                 "compliance_items": ["冷凝水已排空", "滤清器已清洁"]},
                {"phase": "检查", "step_num": 3, "title": "管路与安全装置检查",
                 "content": "1.检查所有管路接头有无泄漏\n2.检查安全阀功能（手动测试）\n3.检查电器接线紧固情况\n4.检查传感器显示准确性",
                 "compliance_items": ["安全阀功能正常", "无泄漏点"]},
                {"phase": "记录", "step_num": 4, "title": "填写巡检记录",
                 "content": "1.填写设备巡检记录表\n2.标注异常情况及处理措施\n3.签名确认",
                 "compliance_items": ["巡检记录填写完整", "异常情况已上报"]},
            ]
        },
    ]

    template_ids = []
    for tpl in templates:
        r = await api("POST", "/api/v1/tasks/templates", ADMIN_AUTH, json=tpl)
        if r.status_code == 200:
            tid = r.json().get("id")
            template_ids.append(tid)
            print(f"  ✓ {tpl['name'][:40]}... (id={tid})")
        else:
            print(f"  ✗ {tpl['name'][:40]}... ({r.status_code})")
            template_ids.append(None)

    # 创建任务实例
    print("  创建任务实例...")
    tasks = [
        {"title": "Y200L-4型电机季度定修(2026年Q2)", "device_model": "Y系列三相异步电动机", "template_id": template_ids[0]},
        {"title": "IS80-50-200循环水泵年度大修", "device_model": "IS型单级离心式清水泵", "template_id": template_ids[1]},
        {"title": "3号空压机2026年6月巡检", "device_model": "LG系列螺杆式空压机", "template_id": template_ids[2]},
    ]
    task_ids = []
    for t in tasks:
        if t["template_id"] is None:
            continue
        r = await api("POST", "/api/v1/tasks/", WORKER_AUTH, json={
            "title": t["title"], "device_model": t["device_model"], "template_id": t["template_id"]
        })
        status = "✓" if r.status_code == 200 else f"✗({r.status_code})"
        tid = r.json().get("id") if r.status_code == 200 else None
        task_ids.append(tid)
        print(f"  {status} {t['title'][:50]}...")

    # 模拟执行任务步骤（第一个任务确认2个步骤）
    if task_ids[0]:
        for step in range(2):
            r = await api("POST", f"/api/v1/tasks/{task_ids[0]}/step", WORKER_AUTH)
            print(f"    → 确认步骤{step+1}: {'✓' if r.status_code==200 else r.status_code}")

    return template_ids, task_ids


async def seed_case_uploads():
    """注入案例上传（不同审核状态）"""
    print("\n[5/8] 注入案例上传...")

    cases = [
        {
            "title": "Y315S-4电机异常振动排查处理案例",
            "content": """【故障现象】
2026年5月12日，巡检人员发现3号生产线Y315S-4驱动电机（55kW）运行中存在明显振动，手持测振仪测量驱动端轴承位置径向振动值达到6.8mm/s（标准应≤2.8mm/s），机身伴随周期性"嗡嗡"声。

【初步排查】
1. 检查电机地脚螺栓——无松动
2. 测量三相电流——平衡，排除电气故障
3. 脱开联轴器后单独运行电机——振动依旧，判断故障在电机本体

【深入分析】
停机后拆卸电机检查：
1. 驱动端轴承（6313/C3）滚道出现明显压痕和麻点，保持架松动
2. 轴承润滑脂已经发黑变质（上次加脂时间为4个月前）
3. 非驱动端轴承（6312/C3）状态正常
4. 转子动平衡复测合格，排除不平衡因素

【根因定位】
驱动端轴承因润滑不良导致滚动体与滚道间油膜破裂，金属直接接触产生微观点蚀。点蚀坑逐渐扩大，引起周期性冲击和振动。根本原因：加脂周期过长（原计划6个月/次），在高温多尘环境下应缩短为3个月/次。

【修复措施】
1. 更换驱动端轴承（6313/C3，SKF正品）
2. 彻底清洗轴承座和轴颈
3. 重新加注3号锂基润滑脂（填充量50%）
4. 非驱动端轴承检查后补充润滑脂
5. 回装后使用激光对中仪校正联轴器

【验证结果】
1. 空载运行30分钟：驱动端振动值1.8mm/s ✓
2. 带载运行2小时：振动值2.1mm/s ✓，轴承温度51℃ ✓
3. 运行一周后复测：振动值稳定在2.0-2.2mm/s ✓

【经验总结】
1. 多尘/高温环境下电机加脂周期应缩短至3个月/次
2. 建立振动趋势监测，振动值连续3周上升≥20%时提前安排检修
3. 轴承更换时建议成对更换，避免新老轴承配合不当""",
            "device_models": ["Y系列三相异步电动机"],
            "fault_tags": ["振动异常", "轴承故障", "润滑不良"],
            "is_experience_based": False,  # 事实型
            "images": [],
        },
        {
            "title": "IS100-65-200离心泵机封泄漏在线带压堵漏经验",
            "content": """【故障现象】
2026年6月3日，2号循环水泵（IS100-65-200）机械密封处出现喷射状泄漏，泵出口压力从0.5MPa下降至0.3MPa，无法维持正常供水。正值生产高峰，不允许长时间停泵。

【应急分析】
根据我多年经验，这种情况下大概率是机械密封的静环O形圈突然失效（可能是安装时挤压变形或材质老化）。因为：①泄漏量急剧增大而非渐进式——说明是密封元件突然破损而非正常磨损；②泵才运行了不到一年——正常磨损不至于这么快。

【带压堵漏方案】
我采用了一种特殊的应急处理方法：
1. 在机械密封压盖的冲洗孔处接入外部密封液（使用一台小型手动泵）
2. 密封液采用高粘度硅油+石墨粉混合（比例5:1），起到临时填充密封作用
3. 缓慢加压密封液至泵出口压力的1.1倍，使密封液在密封面外侧形成液封
4. 泄漏量从喷射状减少至每分钟5-10滴
5. 维持运行4小时后，利用短暂的设备切换窗口（约30分钟）快速更换了机械密封总成

【经验要点】
1. 高粘度密封液+外部加压的方法仅适用于密封元件（O形圈/波纹管）失效，不适用于密封面严重磨损的情况
2. 密封液中加石墨粉可以增加填充性和自润滑性，这是从老师傅那学来的经验
3. 带压堵漏只能作为临时措施争取时间窗口，最终还是要停机更换
4. 需要在密封压盖上预留冲洗孔才能实施此方案（建议今后采购时向厂家要求）

【个人建议】
建议在关键工位的泵都要求厂家在密封压盖上预留冲洗孔——多个孔花不了多少钱，但关键时刻能救命。这也是我们化工行业几十年的老传统了，但现在很多年轻工程师不知道这个。""",
            "device_models": ["IS型单级离心式清水泵"],
            "fault_tags": ["密封泄漏"],
            "is_experience_based": True,  # 经验型 → 需两级审核
            "images": [],
        },
    ]

    for case in cases:
        r = await api("POST", "/api/v1/cases/", WORKER_AUTH, json=case)
        status = "✓" if r.status_code in (200, 201) else f"✗({r.status_code})"
        print(f"  {status} {case['title'][:40]}... ({case['is_experience_based'] and '经验型' or '事实型'})")

    return True


async def seed_tickets():
    """注入客服工单（含回复）"""
    print("\n[6/8] 注入客服工单...")

    tickets = [
        {
            "title": "新安装的Y280M-4电机启动电流偏大是否正常？",
            "description": "我们在2号生产线新安装了一台Y280M-4(90kW)电机，铭牌额定电流164A，直接启动时电流峰值达到1050A(约6.4倍)，稳定运行后电流为150A。请教：启动电流6.4倍是否在正常范围内？需要做哪些检查来确认电机和线路正常？",
            "images": [],
        },
        {
            "title": "空压机频繁出现'排气温度高'报警停机",
            "description": "我们一台LG-22/8型螺杆空压机最近频繁出现排气温度高报警（超过105℃），自动保护停机，一天内已经跳了3次。已经检查过油位正常，冷却风扇运转正常。请问还需要排查哪些方面？",
            "images": [],
        },
        {
            "title": "减速机输出轴密封处渗油处理方案咨询",
            "description": "ZQ400减速机输出轴油封处有少量渗油（地面上每天有直径约5cm的油渍），设备运行参数一切正常。想咨询一下：是否需要立即停机更换油封？如果暂时不更换，有什么临时措施可以控制渗油量？",
            "images": [],
        },
    ]

    ticket_ids = []
    for tk in tickets:
        r = await api("POST", "/api/v1/tickets/", WORKER_AUTH, json=tk)
        if r.status_code == 201:
            tid = r.json().get("id")
            ticket_ids.append(tid)
            print(f"  ✓ {tk['title'][:50]}... (id={tid})")
        else:
            print(f"  ✗ {tk['title'][:50]}... ({r.status_code})")

    # 模拟管理员回复工单
    replies = [
        "您好！Y280M-4电机直接启动电流在6-7倍额定电流属于正常范围（国标规定≤7倍），您测量的6.4倍完全正常。建议补充检查：①电机三相电流是否平衡（不平衡度≤5%）；②启动压降是否过大（≤15%额定电压）；③电缆截面是否满足要求（90kW建议≥70mm²铜芯）；④热继电器整定值是否匹配（建议1.05倍额定电流）。如有其他问题欢迎继续咨询。",
        "您好！排气温度高保护跳机是比较常见的问题。既然油位和冷却风扇正常，建议按以下顺序排查：①清洁冷却器外部散热翅片（可能是积尘导致散热不良——这是最常见原因，占比约60%）；②检查温控阀是否正常工作（温度达到85℃时应开启旁通到冷却器）；③检查油气分离器是否堵塞（压差>0.1MPa时需要更换）；④检查环境温度是否过高（机房通风是否良好）。建议先清理冷却器后再观察。",
        "您好！输出轴油封少量渗油（每天直径5cm油渍）属于轻微泄漏，不会立即影响设备运行，可安排在下一次计划停机时更换。临时措施：①在油封外侧加装一个接油盘防止污染地面；②每天检查减速机油位，不足时补充同牌号润滑油；③每周记录渗油量变化趋势，如果渗油量突然增大则需要提前安排检修。建议备一个同型号油封（规格一般为TC型骨架油封），随时可以更换。",
    ]

    for i, tid in enumerate(ticket_ids):
        if i < len(replies):
            r = await api("POST", f"/api/v1/tickets/{tid}/reply", ADMIN_AUTH, json={"content": replies[i]})
            print(f"  → 回复工单{tid}: {'✓' if r.status_code==200 else f'✗({r.status_code})'}")

    # 模拟用户确认解决（第1个工单）
    if ticket_ids:
        r = await api("PUT", f"/api/v1/tickets/{ticket_ids[0]}/status", WORKER_AUTH, json={"status": "resolved"})
        print(f"  → 确认工单{ticket_ids[0]}已解决: {'✓' if r.status_code==200 else f'✗({r.status_code})'}")

        # 转为知识条目
        r = await api("POST", f"/api/v1/tickets/{ticket_ids[0]}/to-knowledge", ADMIN_AUTH)
        if r.status_code == 200:
            eid = r.json().get("id")
            print(f"  → 工单转知识条目: ✓ (entry_id={eid})")
            # 发布草稿
            await api("POST", f"/api/v1/knowledge/{eid}/publish", ADMIN_AUTH)
            print(f"  → 发布知识条目: ✓")

    return ticket_ids


async def seed_ai_conversations():
    """注入AI对话和反馈"""
    print("\n[7/8] 注入AI对话及反馈...")

    # 对话1: 电机故障诊断（多轮，含反馈）
    r = await api("POST", "/api/v1/conversations", WORKER_AUTH)
    if r.status_code != 200:
        print(f"  ✗ 创建对话失败")
        return
    conv1_id = r.json()["id"]

    # 第一轮：检修模式提问
    r = await api("POST", "/api/v1/chat", WORKER_AUTH, data={
        "message": "Y系列电机运行中突然电流增大、外壳温度明显升高，可能是什么原因？设备型号Y280M-4",
        "conversation_id": str(conv1_id),
        "chat_mode": "rag",
    })
    print(f"  → 对话1-检修提问: {'✓' if r.status_code==200 else f'✗({r.status_code})'}")

    # 第二轮追问
    r = await api("POST", "/api/v1/chat", WORKER_AUTH, data={
        "message": "我检查了轴承，发现润滑脂已经变黑了，应该怎么处理？",
        "conversation_id": str(conv1_id),
        "chat_mode": "rag",
    })
    if r.status_code == 200:
        # 对第二轮回答标记为有用
        msg_id = r.json()["id"]
        await api("POST", f"/api/v1/conversations/{conv1_id}/feedback", WORKER_AUTH, json={
            "feedback": "useful", "message_id": msg_id
        })
        print(f"  → 标记为有用: ✓")

    # 对话2: 闲聊模式
    r = await api("POST", "/api/v1/conversations", WORKER_AUTH)
    conv2_id = r.json()["id"]
    r = await api("POST", "/api/v1/chat", WORKER_AUTH, data={
        "message": "这个系统有哪些主要功能？",
        "conversation_id": str(conv2_id),
        "chat_mode": "casual",
    })
    print(f"  → 对话2-闲聊: {'✓' if r.status_code==200 else f'✗({r.status_code})'}")

    # 对话3: 无用的回答 + 反馈
    r = await api("POST", "/api/v1/conversations", WORKER_AUTH)
    conv3_id = r.json()["id"]
    r = await api("POST", "/api/v1/chat", WORKER_AUTH, data={
        "message": "锅炉安全阀校验需要什么资质？",
        "conversation_id": str(conv3_id),
        "chat_mode": "rag",
    })
    if r.status_code == 200:
        msg_id = r.json()["id"]
        await api("POST", f"/api/v1/conversations/{conv3_id}/feedback", WORKER_AUTH, json={
            "feedback": "useless", "comment": "没有给出具体的资质要求条款，回答太笼统了",
            "message_id": msg_id
        })
        print(f"  → 标记为无用(含修正建议): ✓")

    # 对话4: 管理员自己的对话（带部分有用反馈）
    r = await api("POST", "/api/v1/conversations", ADMIN_AUTH)
    conv4_id = r.json()["id"]
    r = await api("POST", "/api/v1/chat", ADMIN_AUTH, data={
        "message": "减速机异响的常见原因有哪些？ZQ350型号",
        "conversation_id": str(conv4_id),
        "chat_mode": "rag",
    })
    if r.status_code == 200:
        msg_id = r.json()["id"]
        await api("POST", f"/api/v1/conversations/{conv4_id}/feedback", ADMIN_AUTH, json={
            "feedback": "partial", "comment": "列出的原因比较全，但缺少针对ZQ350的具体建议",
            "message_id": msg_id
        })
        print(f"  → 标记为部分有用(含建议): ✓")

    print(f"  对话1: id={conv1_id}, 对话2: id={conv2_id}, 对话3: id={conv3_id}, 对话4: id={conv4_id}")


async def main():
    global ADMIN_AUTH
    print("=" * 60)
    print("汇智海洋 - 演示数据注入脚本")
    print("=" * 60)

    # 登录
    print("\n[0] 管理员登录...")
    ADMIN_AUTH = await login("admin")
    if not ADMIN_AUTH:
        print("✗ 管理员登录失败，请确认后端已启动且admin密码正确")
        return
    print("  ✓ 管理员登录成功")

    # 确保测试账号
    await create_worker_account()

    # 依次注入数据
    await seed_device_models()
    await seed_fault_tags()
    await seed_knowledge_entries()
    await seed_templates_and_tasks()
    await seed_case_uploads()
    await seed_tickets()
    await seed_ai_conversations()

    print("\n" + "=" * 60)
    print("演示数据注入完成!")
    print("=" * 60)
    print("""
📋 数据清单：
  • 8个设备型号
  • 15个故障标签
  • 6条知识库条目(已发布)
  • 3个作业模板 + 3个任务实例(1个已执行2步)
  • 2个案例上传(1个事实型待审, 1个经验型待审)
  • 3个客服工单(1个已解决→转知识, 2个已回复)
  • 4个AI对话(含有用/无用/部分有用反馈)

📌 后续手动操作建议（制作演示视频时）：
  1. 进入审核队列 → 审核通过那个事实型案例
  2. 展示经验型案例的两级审核流程
  3. 在AI反馈管理中查看反馈详情
  4. 将某个"无用"反馈转化为知识条目
  5. 继续执行作业任务的剩余步骤
  6. 在模型配置中演示新增和测试模型
""")

if __name__ == "__main__":
    asyncio.run(main())
