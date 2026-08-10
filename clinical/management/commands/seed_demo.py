"""Populate the demo database with fictional data.

Nothing here comes from a real hospital.  Names, chart numbers, wards, reports
and organisms are generated from the fixed word lists below, with a seeded RNG
so repeated runs produce the same demo content.

    python manage.py seed_demo            # fill an empty database
    python manage.py seed_demo --reset    # wipe demo rows first
"""

import random
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile, Section, SectionPermission, TopicPermission
from clinical.models import (
    Bacteria,
    ClinicalEvent,
    Division,
    CultureIsolate,
    ExamReport,
    MedType,
    Patient,
    SusceptibilityResult,
    Tube,
    VitalMeasurement,
    VitalSign,
    Ward,
)
from infection.models import (
    CategoryPoolEntry,
    ConversionCategory,
    ConversionEntry,
    InfectionCategory,
    Token,
)
from research.models import (
    DiseaseGroup,
    ExamStudy,
    PatientDisease,
    ResearchTopic,
    StageConfirmation,
    StageDefinition,
)

NEWLINE = chr(10)

SURNAMES = ['陳', '林', '黃', '張', '李', '王', '吳', '劉', '蔡', '楊', '許', '鄭', '謝', '洪', '郭']
GIVEN_NAMES = [
    '志明', '淑芬', '家豪', '雅婷', '俊傑', '怡君', '建宏', '美玲', '冠廷', '欣怡',
    '宗翰', '佩珊', '柏翰', '筱涵', '承恩', '思妤', '品睿', '詩涵', '威廷', '若瑄',
]

DIVISIONS = [
    ('IM', '內科'),
    ('SU', '外科'),
    ('ICU', '重症醫學科'),
    ('ID', '感染科'),
    ('ONC', '腫瘤科'),
]

WARDS = [
    ('3A', '內科 3A 病房', 'IM'),
    ('3B', '內科 3B 病房', 'IM'),
    ('5A', '外科 5A 病房', 'SU'),
    ('7C', '腫瘤 7C 病房', 'ONC'),
    ('ICU1', '加護病房 1', 'ICU'),
    ('ICU2', '加護病房 2', 'ICU'),
]

MED_TYPES = [
    (2131, '入院', MedType.Category.ADMISSION),
    (2132, '轉床', MedType.Category.ADMISSION),
    (2133, '出院', MedType.Category.ADMISSION),
    (30401, '護理紀錄', MedType.Category.NURSING),
    (30402, '交班紀錄', MedType.Category.NURSING),
    (30903, '導管留置', MedType.Category.TUBE),
    (30501, '異常生理評值', MedType.Category.VITAL),
]

BACTERIA = [
    ('Escherichia coli', False),
    ('Klebsiella pneumoniae', False),
    ('Staphylococcus aureus', False),
    ('Pseudomonas aeruginosa', False),
    ('Acinetobacter baumannii', False),
    ('Enterococcus faecalis', False),
    ('Candida albicans', False),
    ('Staphylococcus epidermidis', True),
    ('Corynebacterium species', True),
]

CANONICAL_TUBES = [
    'Central venous catheter',
    'Foley catheter',
    'Endotracheal tube',
    'Nasogastric tube',
    'Chest tube',
    'Arterial line',
    'Peripherally inserted central catheter',
]

# Raw spellings that a reviewer maps onto the canonical names above.
TUBE_VARIANTS_A = [
    'CVC', 'C.V.C.', 'central line', 'Foley', 'foley cath', 'F/C',
    'ETT', 'E.T. tube', 'NG tube', 'N-G tube', 'chest tube (R)', 'A-line',
    'PICC line',
]
TUBE_VARIANTS_B = [
    'CV catheter', 'CVP line', 'urinary catheter', 'Foley catheter (16Fr)',
    'endotracheal', 'ET-tube', 'Levin tube', 'pigtail', 'arterial cath', 'PICC',
]

INFECTION_CATEGORIES = ['泌尿道感染', '呼吸道感染', '血流感染', '手術部位感染', '腸胃道感染']

TOKENS_BY_CATEGORY = {
    '泌尿道感染': ['urine culture', 'pyuria', 'dysuria', 'urinary frequency', 'CAUTI',
                   'bladder irrigation', 'nitrite positive'],
    '呼吸道感染': ['sputum culture', 'productive cough', 'infiltration', 'VAP',
                   'oxygen desaturation', 'chest x-ray patchy'],
    '血流感染': ['blood culture', 'bacteremia', 'CLABSI', 'septic shock',
                 'positive 2 sets', 'catheter tip culture'],
    '手術部位感染': ['wound discharge', 'surgical site', 'dehiscence',
                     'purulent drainage', 'erythema around wound'],
    '腸胃道感染': ['stool culture', 'C. difficile', 'diarrhea', 'abdominal pain',
                   'toxin assay positive'],
}

CULTURE_TESTS = [
    ('Blood aerobic & anaerobic culture', 'peripheral blood'),
    ('Urine culture', 'midstream urine'),
    ('Sputum culture', 'expectorated sputum'),
    ('Pus aerobic & anaerobic culture', 'deep abscess'),
    ('Wound culture', 'surgical wound discharge'),
    ('Catheter tip culture', 'central venous catheter tip'),
    ('Stool culture', 'stool'),
]

# Gram-negative and gram-positive panels are reported separately in practice,
# so each organism draws from the panel that matches it.
GRAM_NEGATIVE_PANEL = [
    'Ampicillin', 'Amoxicillin/Clavulanic acid', 'Piperacillin/Tazobactam',
    'Cefazolin', 'Cefuroxime', 'Cefmetazole', 'Ceftriaxone', 'Ceftazidime',
    'Cefepime', 'Flomoxef', 'Ertapenem', 'Imipenem', 'Gentamicin', 'Amikacin',
    'Ciprofloxacin', 'Levofloxacin', 'Trimethoprim/Sulfamethoxazole',
    'Tigecycline', 'Colistin',
]

GRAM_POSITIVE_PANEL = [
    'Penicillin', 'Oxacillin', 'Ampicillin', 'Cefazolin', 'Clindamycin',
    'Erythromycin', 'Gentamicin', 'Levofloxacin', 'Linezolid',
    'Trimethoprim/Sulfamethoxazole', 'Teicoplanin', 'Vancomycin',
]

FUNGAL_PANEL = [
    'Amphotericin B', 'Fluconazole', 'Voriconazole', 'Caspofungin',
    'Micafungin', 'Flucytosine',
]

GRAM_POSITIVE_ORGANISMS = {
    'Staphylococcus aureus', 'Enterococcus faecalis',
    'Staphylococcus epidermidis', 'Corynebacterium species',
}
FUNGAL_ORGANISMS = {'Candida albicans'}

MIC_VALUES = ['<=0.25', '<=0.5', '<=1', '2', '4', '8', '16', '>=32', '>=64']

COLONY_COUNTS = [
    '>100,000 CFU/mL', '50,000–100,000 CFU/mL', '10,000–50,000 CFU/mL',
    'Moderate growth', 'Heavy growth', 'Light growth',
]

CULTURE_COMMENTS = [
    '本菌對第三代頭孢菌素呈抗藥，臨床上請參考感染科建議調整用藥。',
    '分離菌株疑似為 ESBL 產生菌，已加驗確認中。',
    '檢出菌種為皮膚常在菌，須與採檢污染區分；建議重新採檢確認。',
    '同一病患另一套血液培養亦分離出相同菌種，臨床意義高。',
    '菌量偏低，請結合臨床症狀判讀。',
]

# Narrative note skeletons.
#
# Ward notes run long: an admission note carries the route of arrival, the
# working diagnosis, the labs and imaging behind it, past medical and surgical
# history, current vital signs and the plan — several hundred characters in one
# unbroken paragraph.  The templates below are built to that length so the
# 原始報告 view shows realistically dense source text.

ADMISSION_TEMPLATE = (
    '病人於{admit_date}經由急診以{chief}入院，入院診斷為{diagnosis}。'
    '病人於{prior_date}因{prior_reason}住院，出院後於門診追蹤，'
    '近期因{trigger}，家屬訴{symptom}情形持續約{days}天未緩解，'
    '故於今日至本院急診就診。急診抽血檢查 CBC/DC 顯示白血球 {wbc} /uL、'
    'CRP {crp} mg/L，{culture_note}；CXR 顯示{cxr}，'
    '急診醫師評估後認為有感染跡象，經評估後收治入院治療，'
    '診斷為 {diagnosis_en}（{diagnosis}）。'
    '內科病史：{med_history}；外科病史：{surg_history}。'
    '目前病人意識{consciousness}，{vitals_summary}，'
    '已建立靜脈通路並依醫囑給予{treatment}，'
    '入院時已完成護理評估與跌倒風險評估，'
    '並向主要照顧者說明病房環境、訪客時間及呼叫鈴使用方式，'
    '照顧者表示了解。藥物過敏史：{allergy}，已於病歷及手圈註記。'
    '因病人{isolation_reason}，依感染管制規範採{isolation}，'
    '已於床頭張貼標示並衛教家屬入室前後執行手部衛生、'
    '離開病室前脫除防護裝備，家屬回覆示教正確。'
    '本次入院已抽送血液培養兩套及尿液培養，報告尚未回覆，'
    '待報告回覆後再依感染科建議調整抗生素種類與劑量。'
    '持續觀察生命徵象變化、意識狀態、尿量及有無新增感染徵象，'
    '如有異常立即通報醫師處理，並依醫囑每四小時測量生命徵象一次。'
)

SHIFT_TEMPLATE = (
    '本班接手時病人意識{consciousness}，可{communication}，'
    '主訴{symptom}，較前一班{trend}。'
    '{tube_note}管路留置中，插入部位無紅腫熱痛及異常分泌物，'
    '固定良好，管路照護已依標準流程執行並記錄留置天數。'
    '本班依醫囑給予{treatment}，給藥後觀察無藥物過敏反應，'
    '{vitals_summary}。'
    '{culture_note}'
    '進食狀況{intake}，尿量約 {urine} mL/8hr，顏色清澈無異味，'
    '排便{bowel}。皮膚完整性尚可，'
    '已協助翻身拍背每兩小時一次並使用氣墊床預防壓瘡。'
    '疼痛評估以數字量表評估為 {pain} 分，'
    '{pain_action}。'
    '周邊靜脈留置針於{iv_site}，'
    '注射部位無紅腫、滲漏及靜脈炎徵象，'
    '依規定每 72 小時更換一次，本班已確認留置日期。'
    '氧氣使用情形：{oxygen}，血氧維持於目標範圍內。'
    '家屬於會客時間前來探視，已再次說明目前治療計畫與注意事項，'
    '衛教家屬勿自行調整管路及點滴速度，家屬表示了解並配合。'
    '持續監測生命徵象與感染徵象，異常時立即通報值班醫師，'
    '並於下一班交班時說明本班處置及病人反應。'
)

EVENT_TEMPLATE = (
    '{time_of_day}護理人員例行巡視時發現病人{symptom}，'
    '主訴不適，隨即加測生命徵象，{vitals_summary}。'
    '立即通知值班醫師到場評估，醫師開立醫囑：{orders}。'
    '已依醫囑執行並抬高床頭 30 度、給予氧氣使用，'
    '{culture_note}'
    '處置後 30 分鐘複測生命徵象，病人表示不適感較前緩解，'
    '意識{consciousness}，可正確應答，'
    '持續以生理監視器監測心律、血壓及血氧變化，'
    '並將本次異常事件及處置經過交班予下一班護理人員，'
    '囑其密切觀察有無再次發生類似情形。'
    '已依醫囑重新抽送血液培養兩套，並追蹤 CBC/DC 與 CRP 變化，'
    '報告回覆後將立即通知主治醫師評估是否調整抗生素。'
    '同時檢視病人身上各項侵入性管路留置必要性，'
    '與醫師討論可否儘早移除以降低感染風險，'
    '已完成本次異常事件之護理紀錄並登錄於病安通報系統，'
    '後續依單位規範進行個案討論與追蹤。'
)

CHIEF_COMPLAINTS = ['發燒、寒顫', '呼吸急促合併喘鳴', '意識改變', '腹痛合併嘔吐', '傷口紅腫滲液']
PRIOR_REASONS = ['泌尿道感染', '肺炎', '蜂窩性組織炎', '術後傷口感染', '菌血症']
TRIGGERS = ['留置導尿管期間出現發燒', '化療後白血球低下', '術後傷口癒合不良',
            '長期臥床合併吸入性風險', '免疫抑制劑使用中']
CXR_FINDINGS = ['右下肺葉浸潤增加', '兩側肺野斑點狀陰影', '左下肺葉實質化',
                '肺紋increase、未見明顯實質化', '雙側肋膜腔少量積液']
DIAGNOSES_EN = [
    'Bronchopneumonia, unspecified organism',
    'Urinary tract infection, site not specified',
    'Sepsis, unspecified organism',
    'Cellulitis of unspecified site',
    'Surgical site infection, superficial incisional',
]
MED_HISTORIES = ['高血壓、第二型糖尿病，規則服藥中', '慢性腎病第三期，門診追蹤中',
                 '心房顫動，長期使用抗凝血劑', '慢性阻塞性肺病，冬季易急性發作',
                 '無特殊內科病史']
SURG_HISTORIES = ['膽囊切除術於 2019 年 3 月', '脊椎減壓術於 2020 年 5 月',
                  '右側全膝關節置換術於 2021 年 8 月', '腹腔鏡闌尾切除術於 2018 年',
                  '否認過去手術病史']
CONSCIOUSNESS = ['清楚', '清楚但略顯倦怠', '嗜睡但可喚醒', '清楚，定向感完整']
COMMUNICATION = ['正確應答', '自行表達需求', '以點頭搖頭表達', '簡單對話']
TRENDS = ['改善', '無明顯變化', '略為加重']
TREATMENTS = ['靜脈抗生素 Ceftriaxone 1g Q12H', '靜脈輸液 N/S 500mL 維持',
              '退燒藥 Acetaminophen 500mg PO', '氧氣鼻導管 3L/min 使用']
ORDERS = ['抽血送血液培養兩套、CBC/DC 及 CRP', '安排胸部 X 光攝影',
          '給予退燒藥並持續監測體溫', '調整輸液速度並追蹤尿量']
INTAKES = ['普通飲食可進食約八分', '因食慾不佳僅進食約三分', '以鼻胃管灌食配方奶']
BOWELS = ['正常，每日一次', '較硬，已給予軟便劑', '未解，已通知醫師']
TIMES_OF_DAY = ['大夜班', '小夜班', '白班', '交班前']
ALLERGIES = ['否認食物及藥物過敏', 'Penicillin 過敏（皮疹）',
             'Sulfa 類藥物過敏（蕁麻疹）', '海鮮類過敏']
ISOLATION_REASONS = ['痰液培養檢出多重抗藥性菌株', '疑似接觸傳染性疾病',
                     '免疫功能低下需保護性隔離', '腹瀉待排除感染性腸炎']
ISOLATIONS = ['接觸隔離', '飛沫隔離', '保護性隔離']
PAIN_ACTIONS = ['未達給藥標準，續觀察', '已依醫囑給予止痛藥並於 30 分鐘後複評',
                '採非藥物措施給予姿勢擺位及冷敷']
IV_SITES = ['左前臂', '右前臂', '左手背', '右手肘窩']
OXYGENS = ['鼻導管 3L/min 使用中', '面罩 5L/min 使用中', '未使用氧氣，室內空氣下'] 
SYMPTOMS = ['畏寒發抖', '呼吸急促', '倦怠無力', '傷口疼痛', '解尿灼熱感',
            '食慾不佳', '咳嗽有痰', '頭暈', '意識較不清', '冒冷汗']
DIAGNOSES = ['泌尿道感染', '肺炎', '蜂窩性組織炎', '菌血症', '術後傷口感染']

DISEASE_GROUPS = ['肺癌', '大腸直腸癌', '乳癌', '肝癌', '頭頸癌']

RESEARCH_TOPICS = [
    ('肺結節追蹤研究', '收集肺部結節個案的追蹤影像與病理結果，用於分期模型建立。'),
    ('術後感染風險分析', '分析手術個案的術後感染事件與導管留置天數之關聯。'),
    ('腫瘤治療反應評估', '追蹤腫瘤個案於治療前後的檢查紀錄，評估治療反應。'),
]

STAGES = ['疑似', '確診', '治療中', '緩解', '復發']

STUDY_TYPES = [
    ('CT', 'Chest CT with contrast'),
    ('MRI', 'Abdomen MRI'),
    ('PET', 'Whole body PET-CT'),
    ('CT', 'Brain CT without contrast'),
]

HOSPITALS = ['總院', '分院']


class Command(BaseCommand):
    help = '以虛構資料填入示範資料庫'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true', help='先清除既有的示範資料再重新產生'
        )
        parser.add_argument(
            '--patients', type=int, default=40, help='要產生的病患人數（預設 40）'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(20260808)

        if options['reset']:
            self.stdout.write('清除既有示範資料…')
            for model in (
                StageConfirmation, StageDefinition, ExamStudy, PatientDisease,
                ResearchTopic, DiseaseGroup, ConversionEntry, ConversionCategory,
                CategoryPoolEntry, InfectionCategory, Token, SusceptibilityResult,
                CultureIsolate, ExamReport, VitalMeasurement, VitalSign,
                ClinicalEvent, Tube, Patient, Ward, Division, MedType, Bacteria,
            ):
                model.objects.all().delete()
            TopicPermission.objects.all().delete()
            SectionPermission.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        if Patient.objects.exists() and not options['reset']:
            self.stdout.write(self.style.WARNING(
                '資料庫已有資料，未做任何變更。要重新產生請加上 --reset。'
            ))
            return

        divisions = self._create_divisions()
        wards = self._create_wards(divisions)
        med_types = self._create_med_types()
        bacteria = self._create_bacteria()
        patients = self._create_patients(rng, wards, options['patients'])
        self._create_events(rng, patients, med_types, bacteria, wards, divisions)
        self._create_tubes(rng)
        self._create_infection_terms(rng)
        topics = self._create_research(rng, patients)
        self._create_users(topics)

        self.stdout.write(self.style.SUCCESS(
            f'完成：{Patient.objects.count()} 位虛構病患、'
            f'{ClinicalEvent.objects.count()} 筆臨床事件、'
            f'{ExamReport.objects.count()} 份報告。'
        ))

    # -- builders ----------------------------------------------------------

    def _create_divisions(self):
        return {
            code: Division.objects.create(code=code, name=name)
            for code, name in DIVISIONS
        }

    def _create_wards(self, divisions):
        return [
            Ward.objects.create(code=code, name=name, division=divisions[div])
            for code, name, div in WARDS
        ]

    def _create_med_types(self):
        return [
            MedType.objects.create(
                code=code, type_name=name, event_category=category, source='示範資料'
            )
            for code, name, category in MED_TYPES
        ]

    def _create_bacteria(self):
        return [
            Bacteria.objects.create(name=name, is_commensal=commensal)
            for name, commensal in BACTERIA
        ]

    def _create_patients(self, rng, wards, count):
        patients = []
        for index in range(count):
            name = rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES)
            birth = datetime(1940, 1, 1) + timedelta(days=rng.randint(0, 27000))
            patients.append(Patient.objects.create(
                chart_no=f'{9000000 + index * 37:07d}',
                name=name,
                gender=rng.choice([Patient.Gender.MALE, Patient.Gender.FEMALE]),
                birth_date=birth.date(),
                ward=rng.choice(wards),
            ))
        return patients

    def _create_events(self, rng, patients, med_types, bacteria, wards, divisions):
        division_list = list(divisions.values())
        base = timezone.now() - timedelta(days=240)

        for patient in patients:
            admitted = base + timedelta(days=rng.randint(0, 150))
            event_count = rng.randint(6, 14)
            patient_events = []

            for step in range(event_count):
                med_type = rng.choice(med_types)
                exec_date = admitted + timedelta(
                    days=step * rng.randint(1, 3), hours=rng.randint(0, 23)
                )
                organism = (
                    rng.choice(bacteria)
                    if rng.random() < 0.45 and med_type.event_category != MedType.Category.VITAL
                    else None
                )

                event = ClinicalEvent.objects.create(
                    patient=patient,
                    med_type=med_type,
                    exec_date=exec_date,
                    visit_no=f'V{rng.randint(100000, 999999)}',
                    order_no=f'O{rng.randint(100000, 999999)}',
                    item_no=f'I{rng.randint(1000, 9999)}',
                    ward=patient.ward if rng.random() < 0.75 else rng.choice(wards),
                    division=rng.choice(division_list),
                    bacteria=organism,
                )

                vital = None
                if med_type.event_category == MedType.Category.VITAL:
                    vital = VitalSign.objects.create(
                        event=event, **self._abnormal_reading(rng)
                    )
                elif med_type.event_category == MedType.Category.NURSING:
                    vital = VitalSign.objects.create(
                        event=event, **self._routine_reading(rng)
                    )

                if organism is not None and rng.random() < 0.75:
                    self._create_culture_report(rng, event, organism, exec_date, bacteria)

                if vital is not None:
                    self._create_narrative_report(
                        rng, event, vital, exec_date, med_type.event_category
                    )

                patient_events.append(event)

            # Charted once per patient, over all their records.
            self._create_vital_chart(rng, patient, patient_events)

    def _routine_reading(self, rng):
        """A scheduled observation, usually within range.

        A routine round does sometimes catch an abnormal value — that is how an
        異常生理評值 record comes to be opened in the first place — so a small
        share of these readings are out of range too.
        """
        reading = {
            'temperature': round(rng.uniform(36.1, 37.8), 1),
            'blood_pressure': f'{rng.randint(96, 148)}/{rng.randint(56, 90)}',
            'pulse': rng.randint(58, 108),
            'spo2': rng.randint(92, 100),
        }
        if rng.random() < 0.12:
            field = rng.choice(['temperature', 'blood_pressure', 'spo2', 'pulse'])
            if field == 'temperature':
                reading['temperature'] = round(rng.uniform(38.0, 38.8), 1)
            elif field == 'blood_pressure':
                reading['blood_pressure'] = f'{rng.randint(78, 89)}/{rng.randint(42, 60)}'
            elif field == 'spo2':
                reading['spo2'] = rng.randint(86, 89)
            else:
                reading['pulse'] = rng.randint(121, 132)
        return reading

    def _abnormal_reading(self, rng):
        """A reading that triggered an 異常生理評值 record.

        This record type exists *because* an observation fell outside the
        reference range, so at least one field is always out of range —
        otherwise the record would have no reason to exist.  Which field is
        abnormal varies, and more than one may be.
        """
        reading = self._routine_reading(rng)

        options = ['fever', 'hypotension', 'hypoxia', 'tachycardia']
        triggers = rng.sample(options, rng.randint(1, 2))

        if 'fever' in triggers:
            reading['temperature'] = round(rng.uniform(38.0, 39.9), 1)
        if 'hypotension' in triggers:
            reading['blood_pressure'] = f'{rng.randint(70, 89)}/{rng.randint(38, 60)}'
        if 'hypoxia' in triggers:
            reading['spo2'] = rng.randint(84, 89)
        if 'tachycardia' in triggers:
            reading['pulse'] = rng.randint(121, 140)

        return reading

    def _create_culture_report(self, rng, event, organism, exec_date, all_bacteria):
        """A microbiology report: specimen header plus one panel per isolate."""
        collected = exec_date + timedelta(hours=rng.randint(0, 6))
        test_name, specimen = rng.choice(CULTURE_TESTS)
        report = ExamReport.objects.create(
            event=event,
            kind=ExamReport.Kind.CULTURE,
            report_no=f'M{rng.randint(1000000, 9999999)}',
            exec_time=collected + timedelta(days=rng.randint(2, 4)),
            test_name=test_name,
            specimen=specimen,
            collected_at=collected,
            received_at=collected + timedelta(hours=rng.randint(1, 5)),
            content=rng.choice(CULTURE_COMMENTS),
        )

        # Roughly a third of specimens grow a second organism, as mixed
        # cultures do in practice.
        isolates = [organism]
        if rng.random() < 0.35:
            others = [b for b in all_bacteria if b.id != organism.id]
            isolates.append(rng.choice(others))

        for order, isolate_organism in enumerate(isolates):
            isolate = CultureIsolate.objects.create(
                report=report,
                organism=isolate_organism,
                growth=rng.choice([
                    CultureIsolate.Growth.LIGHT,
                    CultureIsolate.Growth.MODERATE,
                    CultureIsolate.Growth.HEAVY,
                ]),
                colony_count=rng.choice(COLONY_COUNTS),
                order=order,
            )
            self._create_panel(rng, isolate, isolate_organism)

        # The plain-text form the lab system would emit.  Written last so it
        # matches the isolates that were actually created.
        report.raw_text = self._culture_raw_text(report)
        report.save(update_fields=['raw_text'])

    def _culture_raw_text(self, report):
        """Render a culture report the way the lab's text export prints it."""
        patient = report.event.patient
        lines = [
            '=' * 62,
            '                    微 生 物 檢 驗 報 告',
            '=' * 62,
            f'病歷號  : {patient.chart_no}',
            f'姓  名  : {patient.name}',
            f'報告編號: {report.report_no}',
            f'檢驗項目: {report.test_name}',
            f'檢體來源: {report.specimen}',
            f'採檢日期: {report.collected_at:%Y/%m/%d %H:%M}',
            f'簽收日期: {report.received_at:%Y/%m/%d %H:%M}',
            f'報告日期: {report.exec_time:%Y/%m/%d %H:%M}',
            '-' * 62,
            'CULTURE RESULT:',
        ]

        for index, isolate in enumerate(report.isolates.all(), start=1):
            lines.append('')
            lines.append(f'  [{index}] {isolate.organism.name} ({isolate.growth})')
            lines.append(f'      COLONY COUNT : {isolate.colony_count}')
            if isolate.organism.is_commensal:
                lines.append('      NOTE         : NORMAL FLORA / POSSIBLE CONTAMINANT')
            lines.append('')
            lines.append('      ANTIBIOTIC                          MIC       RSLT')
            lines.append('      ' + '-' * 52)
            for row in isolate.susceptibilities.all():
                lines.append(
                    f'      {row.antibiotic:<34}{row.mic:<10}{row.interpretation}'
                )

        lines.append('')
        lines.append('-' * 62)
        lines.append('COMMENT:')
        lines.append(f'  {report.content}')
        lines.append('=' * 62)
        lines.append('  S=Susceptible  I=Intermediate  R=Resistant')
        return NEWLINE.join(lines)

    def _create_panel(self, rng, isolate, organism):
        """The antibiotic panel matching the organism's gram stain."""
        if organism.name in FUNGAL_ORGANISMS:
            panel = FUNGAL_PANEL
        elif organism.name in GRAM_POSITIVE_ORGANISMS:
            panel = GRAM_POSITIVE_PANEL
        else:
            panel = GRAM_NEGATIVE_PANEL

        for order, antibiotic in enumerate(panel):
            interpretation = rng.choices(
                [
                    SusceptibilityResult.Interpretation.SUSCEPTIBLE,
                    SusceptibilityResult.Interpretation.INTERMEDIATE,
                    SusceptibilityResult.Interpretation.RESISTANT,
                ],
                weights=[62, 12, 26],
            )[0]
            SusceptibilityResult.objects.create(
                isolate=isolate,
                antibiotic=antibiotic,
                mic=rng.choice(MIC_VALUES),
                interpretation=interpretation,
                order=order,
            )

    def _create_narrative_report(self, rng, event, vital, exec_date, category):
        """A ward progress note: one long, unbroken clinical paragraph."""
        vitals_summary = (
            f'體溫 {vital.temperature}°C、心跳 {vital.pulse} 次/分、'
            f'呼吸 {rng.randint(12, 30)} 次/分、'
            f'血壓 {vital.blood_pressure} mmHg、血氧 {vital.spo2}%'
        )

        organism = event.bacteria
        culture_note = (
            f'血液培養報告顯示 {organism.name} 陽性，已通知醫師調整抗生素，'
            if organism is not None
            else '培養報告尚未回覆，持續追蹤中，'
        )

        if category == MedType.Category.VITAL:
            template, extra = EVENT_TEMPLATE, {
                'time_of_day': rng.choice(TIMES_OF_DAY),
                'orders': rng.choice(ORDERS),
            }
        elif event.med_type.type_name == '入院':
            template, extra = ADMISSION_TEMPLATE, {
                'admit_date': (exec_date - timedelta(hours=rng.randint(2, 10)))
                    .strftime('%Y/%m/%d %H:%M'),
                'chief': rng.choice(CHIEF_COMPLAINTS),
                'prior_date': (exec_date - timedelta(days=rng.randint(30, 240)))
                    .strftime('%Y/%m/%d'),
                'prior_reason': rng.choice(PRIOR_REASONS),
                'trigger': rng.choice(TRIGGERS),
                'days': rng.randint(2, 7),
                'wbc': f'{rng.randint(11, 26) * 1000:,}',
                'crp': round(rng.uniform(18.0, 210.0), 1),
                'cxr': rng.choice(CXR_FINDINGS),
                'diagnosis_en': rng.choice(DIAGNOSES_EN),
                'med_history': rng.choice(MED_HISTORIES),
                'surg_history': rng.choice(SURG_HISTORIES),
                'allergy': rng.choice(ALLERGIES),
                'isolation_reason': rng.choice(ISOLATION_REASONS),
                'isolation': rng.choice(ISOLATIONS),
            }
        else:
            template, extra = SHIFT_TEMPLATE, {
                'communication': rng.choice(COMMUNICATION),
                'trend': rng.choice(TRENDS),
                'tube_note': rng.choice(CANONICAL_TUBES) + ' ',
                'intake': rng.choice(INTAKES),
                'urine': rng.randint(200, 900),
                'bowel': rng.choice(BOWELS),
                'pain': rng.randint(0, 7),
                'pain_action': rng.choice(PAIN_ACTIONS),
                'iv_site': rng.choice(IV_SITES),
                'oxygen': rng.choice(OXYGENS),
            }

        text = template.format(
            vitals_summary=vitals_summary,
            culture_note=culture_note,
            symptom=rng.choice(SYMPTOMS),
            diagnosis=rng.choice(DIAGNOSES),
            consciousness=rng.choice(CONSCIOUSNESS),
            treatment=rng.choice(TREATMENTS),
            **extra,
        )

        kind = (
            ExamReport.Kind.VITAL
            if category == MedType.Category.VITAL
            else ExamReport.Kind.NURSING
        )
        report_no = f'N{rng.randint(1000000, 9999999)}'
        recorded_at = exec_date + timedelta(minutes=rng.randint(5, 90))

        raw = NEWLINE.join([
            f'【{ExamReport.Kind(kind).label}】',
            f'病歷號  : {event.patient.chart_no}',
            f'姓　名  : {event.patient.name}',
            f'記錄編號: {report_no}',
            f'記錄時間: {recorded_at:%Y/%m/%d %H:%M:%S}',
            f'記錄人員: N{rng.randint(10, 99)}',
            f'單　　位: {event.ward.name if event.ward else ""}',
            '-' * 58,
            self._wrap(text, 30),
            '',
            '-' * 58,
            f'BT:{vital.temperature}  PR:{vital.pulse}  '
            f'BP:{vital.blood_pressure}  SPO2:{vital.spo2}%',
        ])

        ExamReport.objects.create(
            event=event,
            kind=kind,
            report_no=report_no,
            exec_time=recorded_at,
            content=text,
            raw_text=raw,
        )

    @staticmethod
    def _wrap(text, width):
        """Hard-wrap CJK text, the way a fixed-width terminal report does."""
        lines = [text[i:i + width] for i in range(0, len(text), width)]
        return NEWLINE.join(lines)

    def _create_vital_chart(self, rng, patient, events):
        """The patient's consolidated vital-sign chart.

        Readings are charted against the patient across the whole stay rather
        than per note, because that consolidated series is what a reviewer
        reads.  Each reading points back at the record it came from.
        """
        charted = [
            e for e in events
            if e.med_type.event_category in (
                MedType.Category.NURSING, MedType.Category.VITAL,
            )
        ]
        if not charted:
            return

        rows = []
        for event in charted:
            # A shift charts several observations around the record's time.
            for _ in range(rng.randint(2, 5)):
                moment = event.exec_date + timedelta(minutes=rng.randint(-180, 300))

                # Nurses often chart only part of a set: a lone temperature, or
                # a blood pressure without a temperature.
                style = rng.choices(['full', 'bp_only', 'temp_only', 'spo2_only'],
                                    weights=[62, 16, 16, 6])[0]
                # Observations charted around an 異常生理評值 record are far
                # more likely to be out of range — that is why the record was
                # opened; routine nursing rounds usually are not.
                abnormal = rng.random() < (
                    0.55 if event.med_type.event_category == MedType.Category.VITAL
                    else 0.12
                )

                row = dict(
                    patient=patient, event=event, measured_at=moment,
                    pulse=None, respiration=None, spo2=None,
                    temperature=None, systolic=None, diastolic=None,
                )

                if style in ('full', 'temp_only'):
                    row['temperature'] = (
                        round(rng.uniform(38.0, 39.9), 1) if abnormal
                        else round(rng.uniform(36.1, 37.8), 1)
                    )
                if style in ('full', 'bp_only'):
                    row['systolic'] = (
                        rng.randint(70, 89) if abnormal else rng.randint(96, 148)
                    )
                    row['diastolic'] = rng.randint(26, 88)
                if style in ('full', 'spo2_only'):
                    row['spo2'] = (
                        rng.randint(84, 89) if abnormal else rng.randint(92, 100)
                    )
                if style == 'full':
                    row['pulse'] = (
                        rng.randint(121, 140) if abnormal else rng.randint(58, 108)
                    )
                    row['respiration'] = (
                        rng.randint(25, 34) if abnormal else rng.randint(12, 22)
                    )
                rows.append(VitalMeasurement(**row))

        VitalMeasurement.objects.bulk_create(rows)

    def _create_tubes(self, rng):
        canonical = []
        for index, name in enumerate(CANONICAL_TUBES, start=1):
            canonical.append(Tube.objects.create(
                tube_no=index, name=name, category=Tube.Category.CANONICAL,
                usage_count=rng.randint(20, 400),
            ))

        next_no = len(canonical) + 1
        for names, category in (
            (TUBE_VARIANTS_A, Tube.Category.VARIANT_A),
            (TUBE_VARIANTS_B, Tube.Category.VARIANT_B),
        ):
            for name in names:
                # Leave roughly a third unmapped so the page has work to show.
                target = rng.choice(canonical) if rng.random() < 0.65 else None
                Tube.objects.create(
                    tube_no=next_no, name=name, category=category,
                    canonical=target, usage_count=rng.randint(1, 90),
                )
                next_no += 1

    def _create_infection_terms(self, rng):
        for category_name in INFECTION_CATEGORIES:
            category = InfectionCategory.objects.create(name=category_name)
            for text in TOKENS_BY_CATEGORY[category_name]:
                token, _ = Token.objects.get_or_create(text=text)
                CategoryPoolEntry.objects.create(
                    category=category,
                    token=token,
                    status=rng.choice([
                        CategoryPoolEntry.Status.PENDING,
                        CategoryPoolEntry.Status.CONFIRMED,
                        CategoryPoolEntry.Status.CONFIRMED,
                    ]),
                )

        # A couple of curated categories so the right-hand list is not empty.
        for name in INFECTION_CATEGORIES[:2]:
            curated = ConversionCategory.objects.create(name=name, pool='感染管控詞庫')
            for text in TOKENS_BY_CATEGORY[name][:3]:
                token = Token.objects.get(text=text)
                ConversionEntry.objects.create(category=curated, token=token)
                CategoryPoolEntry.objects.filter(token=token).update(categorized_count=1)

    def _create_research(self, rng, patients):
        diseases = [DiseaseGroup.objects.create(name=name) for name in DISEASE_GROUPS]

        for patient in patients:
            for disease in rng.sample(diseases, rng.randint(1, 2)):
                PatientDisease.objects.get_or_create(patient=patient, disease=disease)

        # Imaging metadata only — the demo carries no pixel data.
        for patient in patients:
            events = list(patient.events.all())
            for event in rng.sample(events, min(len(events), rng.randint(1, 3))):
                modality, description = rng.choice(STUDY_TYPES)
                ExamStudy.objects.create(
                    event=event,
                    study_id=f'{modality}{rng.randint(100000, 999999)}',
                    series_id=f'S{rng.randint(100, 999)}',
                    description=description,
                    series_description=f'{modality} series',
                    slice_count=rng.randint(40, 320),
                    hospital=rng.choice(HOSPITALS),
                )

        topics = []
        for name, description in RESEARCH_TOPICS:
            topic = ResearchTopic.objects.create(name=name, description=description)
            for order, stage_name in enumerate(STAGES):
                StageDefinition.objects.create(topic=topic, name=stage_name, order=order)
            topics.append(topic)
        return topics

    def _create_users(self, topics):
        """Create demo accounts with different permission levels."""
        accounts = [
            ('demo', 'demo-pass-2026', '示範帳號', [Section.RESEARCH, Section.INFECTION]),
            ('infection', 'demo-pass-2026', '感染管控人員', [Section.INFECTION]),
            ('research', 'demo-pass-2026', '研究助理', [Section.RESEARCH]),
        ]

        for username, password, display_name, sections in accounts:
            if User.objects.filter(username=username).exists():
                continue
            user = User.objects.create_user(
                username=username, password=password, is_active=True
            )
            Profile.objects.create(
                user=user, display_name=display_name, organization='示範單位',
                de_identification=True,
            )
            for section in sections:
                SectionPermission.objects.create(user=user, section=section)
            if Section.RESEARCH in sections:
                for topic in topics:
                    TopicPermission.objects.create(user=user, topic=topic)

        self.stdout.write('示範帳號：demo / infection / research（密碼皆為 demo-pass-2026）')
