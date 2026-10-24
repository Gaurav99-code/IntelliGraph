from __future__ import annotations

from pathlib import Path


OUT = Path(__file__).parent
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT = 54
TOP = 742
BOTTOM = 54
LINE_HEIGHT = 15


DOCUMENTS = {
    "01_diabetes_risk_factors_and_symptoms.pdf": {
        "title": "Type 2 Diabetes: Risk Factors, Symptoms, and Early Detection",
        "subtitle": "Synthetic educational sample for IntelliGraph testing",
        "sections": [
            ("Purpose", [
                "This synthetic review explains how risk factors, early symptoms, and screening markers are connected in type 2 diabetes research. It is created for knowledge graph testing and is not clinical guidance.",
                "Type 2 diabetes develops when insulin resistance and declining beta-cell function combine to produce persistently elevated blood glucose. The condition is influenced by genetics, body composition, sleep, nutrition, physical activity, and social determinants of health.",
            ]),
            ("Risk factors", [
                "Insulin resistance is strongly associated with excess visceral adiposity, low physical activity, and a family history of type 2 diabetes. Hypertension, dyslipidemia, gestational diabetes, and polycystic ovary syndrome are also commonly discussed in risk assessments.",
                "Obesity is not the only pathway to diabetes, but higher adipose tissue can increase inflammatory signaling and make muscle and liver cells less responsive to insulin. The resulting glucose imbalance may remain unnoticed for years.",
                "Social factors also shape risk. Limited access to healthy food, unstable housing, long work hours, and barriers to preventive care can reduce opportunities for exercise, screening, and follow-up.",
            ]),
            ("Symptoms and screening", [
                "Common symptoms may include increased thirst, frequent urination, fatigue, blurred vision, slow wound healing, and recurrent infections. Some people have no obvious symptoms, which is why screening can identify abnormal glucose before complications appear.",
                "Researchers commonly track fasting plasma glucose, the oral glucose tolerance test, and hemoglobin A1c, often written as HbA1c. HbA1c reflects average glycemic exposure over roughly the previous two to three months and is useful for monitoring trends.",
                "A primary care pathway may combine a risk questionnaire with laboratory testing. An abnormal result is generally confirmed or interpreted in context rather than treated as an isolated diagnosis.",
            ]),
            ("Connections for the knowledge graph", [
                "Insulin resistance is connected to obesity, physical inactivity, and elevated blood glucose. HbA1c is connected to screening and long-term glucose monitoring. Early detection is connected to prevention programs, nutrition counseling, and medication decisions.",
            ]),
        ],
    },
    "02_diabetes_treatments_and_medications.pdf": {
        "title": "Type 2 Diabetes: Treatments and Medication Classes",
        "subtitle": "Synthetic educational sample for IntelliGraph testing",
        "sections": [
            ("Overview", [
                "This synthetic document maps treatment strategies used in type 2 diabetes research. It is not a prescribing guide. Treatment selection depends on individual clinical factors, safety considerations, preferences, cost, and monitoring requirements.",
                "Most care pathways begin with nutrition, physical activity, weight management when appropriate, sleep support, and education. Medication is added or adjusted when lifestyle measures alone do not achieve the agreed glycemic target.",
            ]),
            ("Metformin", [
                "Metformin is a widely studied first-line medicine. It primarily reduces hepatic glucose production and can improve insulin sensitivity. Research often compares metformin with newer therapies while considering effectiveness, tolerability, kidney function, and cost.",
                "Gastrointestinal side effects are commonly discussed in studies of metformin. Some patients use a lower starting dose or an extended-release formulation, but decisions belong to a qualified clinician.",
            ]),
            ("GLP-1 receptor agonists", [
                "GLP-1 receptor agonists, including semaglutide, are connected to glucose-dependent insulin secretion, appetite regulation, and weight reduction. Clinical research evaluates their effects on HbA1c, body weight, cardiovascular outcomes, and gastrointestinal tolerability.",
                "The GLP-1 pathway is also related to obesity research because appetite and energy balance can affect insulin resistance. This creates a graph connection between diabetes treatment, weight management, and cardiovascular risk reduction.",
            ]),
            ("Insulin and combination therapy", [
                "Insulin therapy may be considered when glucose levels remain substantially elevated, when beta-cell function declines, or during specific clinical situations. Basal insulin is commonly studied as a way to reduce fasting glucose, while other regimens address meal-related glucose excursions.",
                "Combination therapy connects medication classes with different mechanisms. For example, a clinician may evaluate whether a treatment that improves insulin sensitivity should be combined with a therapy that changes appetite or insulin secretion.",
            ]),
            ("Connections for the knowledge graph", [
                "Metformin is connected to hepatic glucose production and insulin sensitivity. Semaglutide is connected to the GLP-1 receptor pathway, appetite regulation, HbA1c, and weight reduction. Insulin is connected to beta-cell decline and glucose control.",
            ]),
        ],
    },
    "03_diabetes_clinical_research_and_biomarkers.pdf": {
        "title": "Type 2 Diabetes: Clinical Research, Biomarkers, and Outcomes",
        "subtitle": "Synthetic educational sample for IntelliGraph testing",
        "sections": [
            ("Research questions", [
                "Clinical research in type 2 diabetes asks how early disease can be identified, which interventions improve glycemic control, and how treatment changes long-term cardiovascular, kidney, eye, and nerve outcomes.",
                "Randomized controlled trials compare an intervention with a control group, while observational studies analyze patterns in routine care. Meta-analyses combine results from multiple studies when designs and populations are sufficiently comparable.",
            ]),
            ("Biomarkers", [
                "HbA1c is a central biomarker because it summarizes average glycemic exposure. Fasting glucose and post-meal glucose add information about daily variation. Continuous glucose monitoring can provide time-in-range, glucose variability, and low-glucose events.",
                "Researchers also examine lipids, blood pressure, kidney markers such as estimated glomerular filtration rate, and urine albumin. These measures connect diabetes research to cardiovascular and kidney outcome research.",
            ]),
            ("Landmark study patterns", [
                "The Diabetes Prevention Program is often cited in prevention research because it compared intensive lifestyle intervention, metformin, and placebo in people at high risk of diabetes. Its findings connect structured activity, nutrition, weight loss, and delayed disease progression.",
                "Cardiovascular outcome trials have evaluated whether newer glucose-lowering medicines affect major cardiovascular events in addition to HbA1c. These studies connect diabetes medications with heart failure, stroke, myocardial infarction, and kidney outcomes.",
            ]),
            ("Evidence interpretation", [
                "A lower HbA1c does not automatically describe every benefit or harm. Researchers consider adverse events, hypoglycemia, weight change, treatment burden, adherence, patient-reported outcomes, and differences between study populations.",
                "A grounded knowledge base should preserve the document, study population, intervention, comparator, outcome, and limitations that support an answer. This prevents a single result from being presented as universal medical advice.",
            ]),
            ("Connections for the knowledge graph", [
                "HbA1c is connected to glucose monitoring and clinical outcomes. Continuous glucose monitoring is connected to time-in-range and glucose variability. The Diabetes Prevention Program is connected to lifestyle intervention, metformin, and delayed progression.",
            ]),
        ],
    },
    "04_diabetes_nutrition_exercise_and_prevention.pdf": {
        "title": "Type 2 Diabetes: Nutrition, Exercise, and Prevention Pathways",
        "subtitle": "Synthetic educational sample for IntelliGraph testing",
        "sections": [
            ("Prevention framework", [
                "Prevention programs address modifiable risk factors before or soon after abnormal glucose is identified. The strongest programs combine nutrition education, regular physical activity, behavior coaching, monitoring, and follow-up support.",
                "Prevention is not a single diet or exercise prescription. Research compares sustainable patterns that fit a person's culture, resources, schedule, and health status.",
            ]),
            ("Nutrition patterns", [
                "A Mediterranean-style eating pattern emphasizes vegetables, legumes, whole grains, nuts, fruit, fish, and unsaturated fats. Research often connects this pattern to improved diet quality, cardiovascular risk markers, and better insulin sensitivity.",
                "Reducing sugar-sweetened beverages and highly refined carbohydrates can lower rapid glucose exposure for many people. Fiber-rich foods may improve satiety and support a slower rise in post-meal glucose.",
                "Meal planning can be linked to medication timing, glucose monitoring, and weight-management goals. The relevant outcome is usually the overall pattern and sustainability rather than one isolated food.",
            ]),
            ("Exercise and sleep", [
                "Aerobic activity improves cardiorespiratory fitness and can increase glucose uptake by skeletal muscle. Resistance training supports muscle strength and may improve insulin sensitivity by increasing active muscle mass.",
                "Breaking up prolonged sitting is another research theme. Sleep duration and sleep quality are connected to appetite regulation, stress hormones, and insulin resistance, so prevention programs often include sleep routines.",
            ]),
            ("Community prevention", [
                "Community health workers, group education, and digital coaching can improve access to prevention programs. These interventions connect clinical care with schools, workplaces, primary care practices, and local food environments.",
                "The Diabetes Prevention Program provides a research bridge between lifestyle intervention and the risk of progressing from prediabetes to type 2 diabetes. Medication such as metformin may be considered in selected high-risk groups, but prevention plans should remain individualized.",
            ]),
            ("Connections for the knowledge graph", [
                "The Mediterranean-style pattern is connected to fiber, unsaturated fats, cardiovascular risk, and insulin sensitivity. Aerobic activity and resistance training are connected to glucose uptake and prevention. Sleep is connected to appetite regulation and insulin resistance.",
            ]),
        ],
    },
}


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap(text: str, width: int = 88) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def make_pages(document: dict) -> list[list[tuple[str, int, bool]]]:
    pages: list[list[tuple[str, int, bool]]] = []
    page: list[tuple[str, int, bool]] = [(document["title"], 17, True), (document["subtitle"], 9, False), ("", 8, False)]
    y = TOP - 58
    for heading, paragraphs in document["sections"]:
        if y < BOTTOM + 70:
            pages.append(page)
            page = []
            y = TOP
        page.append((heading, 12, True))
        y -= 20
        for paragraph in paragraphs:
            for line in wrap(paragraph):
                if y < BOTTOM + 18:
                    pages.append(page)
                    page = []
                    y = TOP
                page.append((line, 10, False))
                y -= LINE_HEIGHT
            y -= 8
        y -= 5
    if page:
        pages.append(page)
    return pages


def write_pdf(path: Path, document: dict) -> None:
    pages = make_pages(document)
    objects: list[bytes] = []

    def add_object(value: bytes) -> int:
        objects.append(value)
        return len(objects)

    catalog_id = add_object(b"")
    pages_id = add_object(b"")
    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []

    for page_lines in pages:
        commands: list[str] = ["BT"]
        y = TOP
        for line, size, bold in page_lines:
            font = "/F1" if not bold else "/F1"
            commands.append(f"{font} {size} Tf {LEFT} {y} Td ({pdf_escape(line)}) Tj")
            y -= LINE_HEIGHT if size <= 10 else 18
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        content_id = add_object(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        page_ids.append(page_id)

    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>".encode()
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, value in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(value)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    path.write_bytes(output)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, document in DOCUMENTS.items():
        write_pdf(OUT / filename, document)
        print(f"created {filename}")


if __name__ == "__main__":
    main()
