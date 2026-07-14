"""UI Streamlit para los dos componentes de OncoBridge AI."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from onco_bridge import ClinicalPipeline, RadiologyAssistant
from onco_bridge.clinical_assistant import ClinicalAssistant, local_summary


ROOT = Path(__file__).resolve().parent
GT_DIRECTORY = ROOT.parent / "dataset_clinical_only" / "dataset" / "oncology_ground_truth_base"
CONFIG_PATH = ROOT / "best_hyperparameters.json"


@st.cache_resource(show_spinner="Cargando modelo de recuperación clínica…")
def get_pipeline() -> ClinicalPipeline:
    config = {}
    if CONFIG_PATH.exists():
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config = payload.get("best_config", payload)
    return ClinicalPipeline(GT_DIRECTORY, **config)


@st.cache_resource
def get_clinical_assistant() -> ClinicalAssistant:
    return ClinicalAssistant()


@st.cache_resource
def get_radiology_assistant() -> RadiologyAssistant:
    return RadiologyAssistant()


def initialise_state() -> None:
    for key, value in {
        "c1_output": None,
        "c2_output": None,
        "chat": [],
        "generated_summary": None,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_after_c1() -> None:
    st.session_state.c2_output = None
    st.session_state.chat = []
    st.session_state.generated_summary = None


def show_c1(external_consent: bool) -> None:
    assistant = get_clinical_assistant()
    st.header("Componente 1 — Análisis clínico")
    st.write("Cargá el contexto estructurado del paciente para recuperar hipótesis, estimar necesidad de imágenes y orientar el siguiente paso clínico.")
    uploaded = st.file_uploader("Cargar input clínico (JSON)", type="json", key="c1_input")
    if uploaded and st.button("Analizar caso", type="primary", key="analyze_c1"):
        try:
            patient = json.load(uploaded)
            with st.spinner("Analizando contexto clínico…"):
                st.session_state.c1_output = get_pipeline().analyze(patient)
            reset_after_c1()
            if assistant.available and external_consent:
                with st.spinner("Preparando resumen para el médico…"):
                    st.session_state.generated_summary = assistant.answer(st.session_state.c1_output)
            else:
                st.session_state.generated_summary = local_summary(st.session_state.c1_output)
        except (json.JSONDecodeError, ValueError) as error:
            st.error(f"No se pudo leer el input clínico: {error}")
        except Exception as error:
            st.error(f"No se pudo completar el análisis: {error}")

    output = st.session_state.c1_output
    if not output:
        return
    st.subheader("Resumen para el médico")
    st.write(st.session_state.generated_summary or local_summary(output))
    st.caption("La recomendación es apoyo a la decisión; la decisión final corresponde al profesional tratante.")
    with st.expander("Ver detalles del análisis", expanded=False):
        st.write("Recomendación:", output["recommendation"])
        st.write("Urgencia:", output["urgency"])
        st.write("Probabilidad estimada de requerir imagen:", f"{output['imaging_needed_probability']:.0%}")
        for item in output["matched_ground_truths"]:
            st.markdown(f"- **{item['icd_10_description']}** — {item['match_probability']:.0%}")

    st.divider()
    st.subheader("Consultar al asistente")
    st.caption("Ejemplos: “¿Qué evidencia respalda la hipótesis principal?” o “¿Por qué se recomienda la derivación?”")
    if assistant.available and not external_consent:
        st.warning("Para usar el chat generativo, confirmá en la barra lateral que podés enviar el output anonimizado al proveedor de IA.")
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    question = st.chat_input("Escribí una pregunta sobre este caso")
    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            if assistant.available and external_consent:
                with st.spinner("Redactando respuesta…"):
                    reply = assistant.answer(output, question, st.session_state.chat[:-1])
            else:
                reply = "El chat generativo requiere Gemini configurado y la confirmación de envío del output anonimizado."
            st.write(reply)
        st.session_state.chat.append({"role": "assistant", "content": reply})


def show_c2(external_consent: bool) -> None:
    assistant = get_radiology_assistant()
    c1_output = st.session_state.c1_output
    st.header("Componente 2 — Asistencia radiológica")
    st.write("Usa las hipótesis e instrucciones de C1 para orientar la lectura de una imagen cargada por el especialista.")
    st.warning("Las regiones de interés generadas son descriptivas. Esta demo no realiza segmentación pixel a pixel ni reemplaza el informe radiológico.")
    if not c1_output:
        st.info("Primero completá el análisis en Componente 1. Su output es el contexto obligatorio de Componente 2.")
        return

    st.caption(f"Caso activo: {c1_output.get('patient_id', 'sin ID')} — recomendación C1: {c1_output.get('recommendation')}")
    with st.expander("Contexto recibido desde C1", expanded=False):
        st.write(c1_output.get("clinical_summary", ""))
        for item in c1_output.get("matched_ground_truths", []):
            st.markdown(f"- **{item['icd_10_description']}** — {item['match_probability']:.0%}")

    image = st.file_uploader("Cargar estudio de imagen (PNG, JPG o WEBP)", type=["png", "jpg", "jpeg", "webp"], key="c2_image")
    modality = st.selectbox("Modalidad", ["mammography", "CT", "MRI", "ultrasound", "X-ray", "other"], key="c2_modality")
    view = st.text_input("Vista o proyección", placeholder="Ej.: MLO + CC bilateral", key="c2_view")
    acquisition_date = st.date_input("Fecha de adquisición", key="c2_date")
    if image:
        st.image(image.getvalue(), caption=image.name, use_container_width=True)
    if assistant.available and not external_consent:
        st.warning("Para analizar una imagen con Gemini, confirmá en la barra lateral que podés enviar el estudio y el output anonimizado al proveedor de IA.")
    if image and st.button("Analizar estudio de imagen", type="primary", key="analyze_c2"):
        if not assistant.available:
            st.error("Configurá GEMINI_API_KEY en .env antes de ejecutar el Componente 2.")
        elif not external_consent:
            st.error("Se requiere confirmación de envío al proveedor de IA para analizar el estudio.")
        else:
            try:
                with st.spinner("Contrastando el estudio con las hipótesis de C1…"):
                    st.session_state.c2_output = assistant.analyze(
                        c1_output,
                        image.getvalue(),
                        image.type or "image/png",
                        modality,
                        view or "no especificada",
                        acquisition_date,
                    )
            except Exception as error:
                st.error(f"No se pudo completar el análisis radiológico: {error}")

    result = st.session_state.c2_output
    if not result:
        return
    st.subheader("Informe de apoyo radiológico")
    st.write(result["findings"])
    left, right = st.columns(2)
    left.metric("Clasificación", result["classification"])
    right.metric("Confianza estimada", f"{result['confidence']:.0%}")
    st.markdown("**Recomendación de apoyo:** " + result["final_recommendation"])
    if result["next_steps"]:
        st.markdown("**Próximos pasos sugeridos:**")
        for step in result["next_steps"]:
            st.markdown(f"- {step}")
    st.markdown("**Regiones de interés descriptivas:**")
    if result["segmentation"]["regions_of_interest"]:
        st.dataframe(result["segmentation"]["regions_of_interest"], use_container_width=True, hide_index=True)
    else:
        st.write("No se reportaron regiones de interés estructuradas.")
    st.caption(result["limitations"])


st.set_page_config(page_title="OncoBridge AI", page_icon="🩺", layout="centered")
initialise_state()
st.title("OncoBridge AI")
st.caption("Sistema de apoyo a la decisión oncológica. No reemplaza el juicio clínico.")

with st.sidebar:
    st.header("Navegación")
    component = st.radio("Sección", ["Componente 1", "Componente 2"])
    st.divider()
    st.header("Configuración")
    gemini_ready = get_clinical_assistant().available
    st.write("Gemini:", "configurado" if gemini_ready else "no configurado")
    if not gemini_ready:
        st.info("Copiá `.env.example` como `.env` y completá `GEMINI_API_KEY`.")
    st.caption("C1 y los embeddings se ejecutan localmente. C2, el resumen y el chat envían el output o la imagen a Gemini solo si lo confirmás.")
    external_consent = st.checkbox("Confirmo que puedo enviar el output anonimizado y, para C2, el estudio de imagen al proveedor de IA", value=False)

if component == "Componente 1":
    show_c1(external_consent)
else:
    show_c2(external_consent)
