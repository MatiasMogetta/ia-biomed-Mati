"""UI Streamlit para los componentes de OncoBridge AI."""
from __future__ import annotations

import json

import streamlit as st

from onco_bridge import ClinicalPipeline, LocalDiffusionReferenceGenerator
from onco_bridge.clinical_assistant import ClinicalAssistant, local_summary
from onco_bridge.config import DEFAULT_CONFIG_PATH, GT_DIRECTORY, load_pipeline_config


@st.cache_resource(show_spinner="Cargando modelo de recuperación clínica…")
def get_pipeline() -> ClinicalPipeline:
    return ClinicalPipeline(GT_DIRECTORY, **load_pipeline_config(DEFAULT_CONFIG_PATH))


@st.cache_resource
def get_clinical_assistant() -> ClinicalAssistant:
    return ClinicalAssistant()


@st.cache_resource
def get_local_reference_generator() -> LocalDiffusionReferenceGenerator:
    return LocalDiffusionReferenceGenerator()


def initialise_state() -> None:
    for key, value in {"c1_output": None, "chat": [], "generated_summary": None, "generated_reference": None}.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_c1(external_consent: bool) -> None:
    assistant = get_clinical_assistant()
    st.header("Componente 1 — Análisis clínico")
    uploaded = st.file_uploader("Cargar input clínico (JSON)", type="json")
    if uploaded and st.button("Analizar caso", type="primary"):
        try:
            with st.spinner("Analizando contexto clínico…"):
                st.session_state.c1_output = get_pipeline().analyze(json.load(uploaded))
            st.session_state.chat, st.session_state.generated_reference = [], None
            output = st.session_state.c1_output
            st.session_state.generated_summary = assistant.answer(output) if assistant.available and external_consent else local_summary(output)
        except Exception as error:
            st.error(f"No se pudo completar el análisis: {error}")

    output = st.session_state.c1_output
    if not output:
        return
    st.subheader("Resumen para el médico")
    st.write(st.session_state.generated_summary or local_summary(output))
    st.caption("Apoyo a la decisión: la decisión final corresponde al profesional tratante.")
    with st.expander("Ver detalles del análisis"):
        st.write("Recomendación:", output["recommendation"])
        st.write("Urgencia:", output["urgency"])
        for item in output["matched_ground_truths"]:
            st.markdown(f"- **{item['icd_10_description']}** — {item['match_probability']:.0%}")

    st.subheader("Consultar al asistente")
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    question = st.chat_input("Escribí una pregunta sobre este caso")
    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("assistant"):
            reply = assistant.answer(output, question, st.session_state.chat[:-1]) if assistant.available and external_consent else "El chat requiere Gemini configurado y confirmación para enviar el output anonimizado."
            st.write(reply)
        st.session_state.chat.append({"role": "assistant", "content": reply})


def show_c2() -> None:
    st.header("Componente 2 — Guía visual radiológica")
    st.write("Genera localmente una referencia sintética de lo que se espera observar según la hipótesis principal de C1.")
    st.warning("La imagen es educativa, sintética y no corresponde al paciente. No constituye evidencia clínica ni un informe radiológico.")
    output = st.session_state.c1_output
    if not output:
        st.info("Primero completá el análisis en Componente 1.")
        return
    with st.expander("Guía esperada desde C1", expanded=True):
        st.caption("Estos prompts orientan la lectura y la generación sintética; no son hallazgos confirmados del paciente.")
        for item in output.get("matched_ground_truths", []):
            st.markdown(f"- **{item['icd_10_description']}** — {item['match_probability']:.0%}")
            instructions = item.get("radiologist_instructions", {})
            st.markdown("**Qué se espera observar (positive prompt):**")
            st.code(instructions.get("meddiffusion_reference_prompt", "No disponible"), language=None)
            st.markdown("**Qué no se espera observar / evitar (negative prompt):**")
            st.code(instructions.get("meddiffusion_negative_prompt", "No disponible"), language=None)
    if st.button("Generar referencia local (GPU)", type="primary"):
        try:
            with st.spinner("Cargando Stable Diffusion y generando la referencia…"):
                generated = get_local_reference_generator().generate(output)
            st.session_state.generated_reference = generated
        except Exception as error:
            st.error(f"No se pudo generar la referencia local: {error}")
    generated = st.session_state.generated_reference
    if generated:
        st.image(generated.data, caption=f"Stable Diffusion local — {generated.gt_id}", use_container_width=True)
        st.caption(generated.limitation)


st.set_page_config(page_title="OncoBridge AI", page_icon="🩺", layout="centered")
initialise_state()
st.title("OncoBridge AI")
st.caption("Sistema de apoyo a la decisión oncológica. No reemplaza el juicio clínico.")
with st.sidebar:
    component = st.radio("Sección", ["Componente 1", "Componente 2"])
    st.divider()
    ready = get_clinical_assistant().available
    st.write("Gemini (solo chat):", "configurado" if ready else "no configurado")
    external_consent = st.checkbox("Confirmo que puedo enviar el output anonimizado al asistente de texto", value=False)

if component == "Componente 1":
    show_c1(external_consent)
else:
    show_c2()
