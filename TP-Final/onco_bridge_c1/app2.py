"""Interfaz Streamlit end-to-end de OncoBridge AI."""
from __future__ import annotations

import json
from typing import Any

import streamlit as st

from onco_bridge import ClinicalPipeline, LocalDiffusionReferenceGenerator
from onco_bridge.clinical_assistant import ClinicalAssistant, local_summary
from onco_bridge.config import (
    CASES_DIRECTORY,
    DEFAULT_CONFIG_PATH,
    GT_DIRECTORY,
    ensure_semantic_ready,
    load_pipeline_config,
)


PROMPT2MEDIMAGE_MODEL = "Nihirc/Prompt2MedImage"


st.set_page_config(page_title="OncoBridge AI", page_icon="🩺", layout="wide")
st.markdown(
    """
    <style>
    .block-container {max-width: 1380px; padding-top: 1.8rem; padding-bottom: 4rem;}
    [data-testid="stMetric"] {background: #f6f8fb; border: 1px solid #e1e7ef; border-radius: 14px; padding: 16px;}
    [data-testid="stMetricValue"] {font-size: 2rem;}
    .patient-label {color: #65758b; font-size: .82rem; font-weight: 700; letter-spacing: .02em; text-transform: uppercase;}
    .patient-value {font-size: 1rem; margin: .15rem 0 .9rem 0;}
    .app-title {text-align: center; color: #172033; font-size: 3rem; font-weight: 750; letter-spacing: -.04em; margin: .4rem 0 .2rem 0;}
    .app-subtitle {text-align: center; color: #65758b; font-size: 1rem; margin: 0 0 1.8rem 0;}
    .result-card {min-height: 130px; border: 1px solid #e1e7ef; border-radius: 14px; padding: 18px 20px; box-sizing: border-box;}
    .result-card-label {color: #65758b; font-size: .9rem; font-weight: 600; margin-bottom: .8rem;}
    .result-card-value {font-size: 2rem; font-weight: 650; line-height: 1.15;}
    .result-neutral {background: #f6f8fb; color: #1f2937;}
    .result-urgent {background: #fff1f2; border-color: #fecdd3; color: #9f1239;}
    .result-positive {background: #fff1f2; border-color: #fecdd3; color: #9f1239;}
    .result-negative {background: #f0fdf4; border-color: #bbf7d0; color: #166534;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Preparando análisis clínico…")
def get_pipeline() -> ClinicalPipeline:
    pipeline = ClinicalPipeline(GT_DIRECTORY, **load_pipeline_config(DEFAULT_CONFIG_PATH))
    ensure_semantic_ready(pipeline, "La aplicación")
    return pipeline


@st.cache_resource
def get_clinical_assistant() -> ClinicalAssistant:
    return ClinicalAssistant()


@st.cache_resource
def get_local_reference_generator() -> LocalDiffusionReferenceGenerator:
    return LocalDiffusionReferenceGenerator(model_id=PROMPT2MEDIMAGE_MODEL)


@st.cache_data(show_spinner=False)
def load_dataset_cases() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for case_dir in sorted(CASES_DIRECTORY.glob("case_*")):
        input_path = case_dir / "input.json"
        if input_path.exists():
            cases[case_dir.name] = json.loads(input_path.read_text(encoding="utf-8"))
    return cases


def initialise_state() -> None:
    defaults = {
        "analysis_key": None,
        "c1_output": None,
        "c2_output": None,
        "generated_summary": None,
        "generated_reference": None,
        "chat": [],
        "professional_view": "Oncólogo",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clean_label(value: Any) -> str:
    return str(value or "No informado").replace("_", " ").strip().capitalize()


def render_list(items: list[Any], empty: str = "No informado") -> None:
    if not items:
        st.markdown(f"<div class='patient-value'>{empty}</div>", unsafe_allow_html=True)
        return
    for item in items:
        st.markdown(f"- {item}")


def render_patient(patient: dict[str, Any]) -> None:
    demographics = patient.get("demographics", {})
    with st.expander("📋 Datos del paciente", expanded=True):
        identity, clinical, objective = st.columns(3, gap="large")
        with identity:
            st.markdown("<div class='patient-label'>ID del paciente</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='patient-value'>{patient.get('patient_id', 'No informado')}</div>", unsafe_allow_html=True)
            st.markdown("<div class='patient-label'>Edad y sexo</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='patient-value'>{demographics.get('age', 'No informada')} años · {clean_label(demographics.get('sex'))}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<div class='patient-label'>Antecedentes familiares</div>", unsafe_allow_html=True)
            render_list(demographics.get("family_history", []), "Sin antecedentes consignados")
        with clinical:
            st.markdown("<div class='patient-label'>Síntomas actuales</div>", unsafe_allow_html=True)
            render_list(patient.get("current_symptoms", []), "Sin síntomas consignados")
            st.markdown("<div class='patient-label'>Historia clínica</div>", unsafe_allow_html=True)
            history = patient.get("medical_history", [])
            render_list([f"{item.get('date', 'Sin fecha')}: {item.get('event', '')}" for item in history], "Sin eventos consignados")
        with objective:
            st.markdown("<div class='patient-label'>Laboratorio</div>", unsafe_allow_html=True)
            labs = patient.get("current_labs", {})
            render_list([f"**{clean_label(key)}:** {value}" for key, value in labs.items()], "Sin laboratorios consignados")


def render_professional_selector() -> str:
    st.subheader("Seleccioná tu perfil profesional")
    oncologist, radiologist = st.columns(2, gap="large")
    with oncologist:
        with st.container(border=True):
            st.markdown("### 🩺 Oncólogo")
            st.caption("Resumen clínico, hipótesis y consulta al asistente.")
            if st.button(
                "Ingresar como oncólogo",
                key="select_oncologist",
                type="primary" if st.session_state.professional_view == "Oncólogo" else "secondary",
                use_container_width=True,
            ):
                st.session_state.professional_view = "Oncólogo"
    with radiologist:
        with st.container(border=True):
            st.markdown("### 🩻 Radiólogo")
            st.caption("Guía de hallazgos esperados y referencia visual.")
            if st.button(
                "Ingresar como radiólogo",
                key="select_radiologist",
                type="primary" if st.session_state.professional_view == "Radiólogo" else "secondary",
                use_container_width=True,
            ):
                st.session_state.professional_view = "Radiólogo"
    return st.session_state.professional_view


def render_result_card(label: str, value: str, style: str) -> None:
    st.markdown(
        f'<div class="result-card {style}"><div class="result-card-label">{label}</div>'
        f'<div class="result-card-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def run_end_to_end(patient: dict[str, Any], analysis_key: str) -> None:
    assistant = get_clinical_assistant()
    generated = None
    c2_warning = None
    with st.status("Ejecutando OncoBridge AI…", expanded=True) as status:
        status.write("Analizando la historia clínica del paciente.")
        output = get_pipeline().analyze(patient)
        if output.get("recommendation") == "DERIVAR_A_IMAGEN" and output.get("matched_ground_truths"):
            status.write("Preparando la guía visual para el estudio por imágenes.")
            try:
                generated = get_local_reference_generator().generate(output, device="auto")
                c2_output = {
                    "status": "reference_generated",
                    "mode": "prospective_visual_guidance",
                    "gt_id": generated.gt_id,
                    "model": generated.model,
                    "prompt": generated.prompt,
                    "limitation": generated.limitation,
                }
            except Exception as error:
                c2_warning = str(error)
                c2_output = {
                    "status": "generation_unavailable",
                    "mode": "prospective_visual_guidance",
                    "message": "C1 finalizó, pero no fue posible generar la referencia visual local.",
                    "limitation": c2_warning,
                }
        else:
            status.write("No se requiere una guía visual para este caso.")
            c2_output = {
                "status": "not_required",
                "mode": "prospective_visual_guidance",
                "message": "No se generó una referencia porque C1 no recomendó derivación a imágenes.",
            }
        status.write("Preparando la información para el profesional.")
        summary = assistant.answer(output) if assistant.available else local_summary(output)
        status.update(label="Análisis end-to-end completado", state="complete", expanded=False)

    st.session_state.analysis_key = analysis_key
    st.session_state.c1_output = output
    st.session_state.c2_output = c2_output
    st.session_state.generated_summary = summary
    st.session_state.generated_reference = generated
    st.session_state.chat = []
    if c2_warning:
        st.warning(f"El análisis clínico finalizó correctamente, pero no fue posible generar la guía visual: {c2_warning}")


def render_summary(output: dict[str, Any]) -> None:
    st.write(st.session_state.generated_summary or local_summary(output))
    st.caption("Resultado de apoyo a la decisión; no constituye diagnóstico ni reemplaza el juicio profesional.")


def render_hypotheses(matches: list[dict[str, Any]]) -> None:
    if not matches:
        st.info("C1 no encontró evidencia suficiente para sostener una hipótesis de los 30 GT.")
    for index, item in enumerate(matches, start=1):
        with st.container(border=True):
            left, right = st.columns([4, 1])
            left.markdown(f"### {index}. {item['icd_10_description']}")
            left.caption(f"{item['gt_id']} · ICD-10 {item['icd_10']}")
            right.metric("Match", f"{item['match_probability']:.0%}")
            st.progress(float(item["match_probability"]))
            st.write(item.get("match_rationale", "Sin justificación disponible."))


def render_radiology_guide(output: dict[str, Any], matches: list[dict[str, Any]]) -> None:
    if output.get("recommendation") != "DERIVAR_A_IMAGEN":
        st.info("El paciente no fue derivado a imagen. No corresponde generar una guía radiológica sin una hipótesis respaldada.")
        return
    if not matches:
        st.info("No corresponde generar una guía radiológica sin una hipótesis respaldada.")
        return
    primary = matches[0]
    instructions = primary.get("radiologist_instructions", {})
    st.subheader(primary["icd_10_description"])
    modalities = instructions.get("suggested_modalities", [])
    if modalities:
        st.write("**Modalidades sugeridas:** " + ", ".join(modalities))
    expected, avoid = st.columns(2, gap="large")
    with expected:
        st.success("**Qué se espera observar (positive prompt)**")
        st.write(instructions.get("meddiffusion_reference_prompt", "No disponible"))
    with avoid:
        st.warning("**Qué no se espera observar (negative prompt)**")
        st.write(instructions.get("meddiffusion_negative_prompt", "No disponible"))
    location = instructions.get("imaging_location", {})
    if location:
        with st.expander("Región y zonas prioritarias", expanded=True):
            st.write("**Región:**", location.get("body_region", "No disponible"))
            st.write("**Referencias anatómicas:**", location.get("anatomical_landmarks", "No disponibles"))
            render_list(location.get("priority_zones", []), "Sin zonas prioritarias consignadas")
    generated = st.session_state.generated_reference
    if generated:
        _, image_column, _ = st.columns([1, 2, 1])
        with image_column:
            st.image(generated.data, caption=f"Referencia sintética local · {generated.gt_id}", width=560)
        st.caption(generated.limitation)
        st.download_button("Descargar referencia PNG", generated.data, f"reference_{generated.gt_id}.png", "image/png")
    elif st.session_state.c2_output.get("status") == "not_required":
        st.info("No se generó una guía visual porque no se indicó una derivación por imágenes.")
    else:
        st.warning("No se generó la referencia visual. Revisá la disponibilidad de CUDA y PyTorch.")


def render_chat(output: dict[str, Any]) -> None:
    st.subheader("Consultar al asistente")
    st.caption("El chat solo puede utilizar el output de C1; si falta evidencia debe indicarlo.")
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    question = st.chat_input("Preguntá por la evidencia, la derivación o las limitaciones")
    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("assistant"):
            assistant = get_clinical_assistant()
            if assistant.available:
                reply = assistant.answer(output, question, st.session_state.chat[:-1])
            else:
                reply = "El chat generativo requiere configurar GEMINI_API_KEY. El análisis local ya está disponible arriba."
            st.write(reply)
        st.session_state.chat.append({"role": "assistant", "content": reply})


def render_results(professional_view: str) -> None:
    output = st.session_state.c1_output
    if not output:
        return
    matches = output.get("matched_ground_truths", [])
    st.divider()
    if professional_view == "Oncólogo":
        st.header("Resultados del análisis")
        urgency_column, referral_column = st.columns(2, gap="large")
        urgency = clean_label(output.get("urgency"))
        urgency_style = "result-urgent" if output.get("urgency") == "alta" else "result-neutral"
        with urgency_column:
            render_result_card("Urgencia", urgency, urgency_style)
        with referral_column:
            if output.get("recommendation") == "DERIVAR_A_IMAGEN":
                render_result_card("Derivar a imagen", "Derivar a imagen", "result-positive")
            else:
                render_result_card("Derivar a imagen", "No derivar a imagen", "result-negative")
        st.header("Espacio del oncólogo")
        summary_tab, hypotheses_tab = st.tabs(["Resumen clínico", "Hipótesis"])
        with summary_tab:
            render_summary(output)
        with hypotheses_tab:
            render_hypotheses(matches)
        render_chat(output)
    else:
        st.header("Guía radiológica")
        render_radiology_guide(output, matches)


initialise_state()
st.markdown('<div class="app-title">OncoBridge AI</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Herramienta de apoyo para la evaluación oncológica y la orientación radiológica</div>', unsafe_allow_html=True)
professional_view = render_professional_selector()

cases = load_dataset_cases()
selected_case = st.selectbox(
    "Seleccionar paciente de la historia clínica institucional",
    options=list(cases),
    format_func=lambda case_id: f"{case_id} · {cases[case_id].get('patient_id', 'sin ID')}",
)
patient = cases[selected_case]
analysis_key = selected_case

if patient and analysis_key:
    render_patient(patient)
    if st.button("🔍 Analizar caso end-to-end", type="primary", use_container_width=True):
        try:
            run_end_to_end(patient, analysis_key)
        except Exception as error:
            st.error(f"No se pudo completar el análisis: {error}")
    if st.session_state.analysis_key == analysis_key:
        render_results(professional_view)
    elif st.session_state.c1_output:
        st.info("Seleccionaste otro caso. Presioná “Analizar caso end-to-end” para actualizar los resultados.")
else:
    st.info("Seleccioná un paciente de la historia clínica institucional para comenzar.")
