# Healthcare and Medical Research test set

These four PDFs are synthetic, cross-linked documents for testing the
IntelliGraph upload, graph, thematic retrieval, factual retrieval, and source
highlighting flows. They are not medical advice and should not be used for
clinical decisions.

## Files

1. `01_diabetes_risk_factors_and_symptoms.pdf`
2. `02_diabetes_treatments_and_medications.pdf`
3. `03_diabetes_clinical_research_and_biomarkers.pdf`
4. `04_diabetes_nutrition_exercise_and_prevention.pdf`

## Suggested frontend questions

- What are the main themes across these documents?
- How are insulin resistance and obesity connected?
- Which medication is connected to hepatic glucose production?
- How is semaglutide related to weight reduction and HbA1c?
- What did the Diabetes Prevention Program compare?
- How do aerobic activity and resistance training support prevention?
- How are sleep and insulin resistance connected?
- Which biomarkers are used to evaluate diabetes outcomes?

## Regenerate

From the project root:

```powershell
venv\Scripts\python.exe sample_pdfs\generate_samples.py
```
