"""
Environmental and Symptom Scoring Module
Based on the 14 Lancet risk factors for dementia and a self-reported symptom severity index.
"""

def calculate_environmental_score(factors: dict, symptom_severity: float) -> float:
    """
    Calculates the combined environmental and symptom risk score (0.0 to 1.0).
    
    The Lancet commission identified 14 modifiable risk factors for dementia.
    This simple model treats each present risk factor as contributing equally to the 
    environmental risk score, and blends it with self-reported symptom severity.
    
    Args:
        factors: A dictionary of the 14 boolean risk factors.
        symptom_severity: A float between 0.0 and 1.0 representing self-reported symptoms.
        
    Returns:
        float: A composite environmental risk score between 0.0 and 1.0.
    """
    LANCET_FACTORS = [
        "education_less_than_secondary",
        "hearing_loss",
        "hypertension",
        "smoking",
        "obesity",
        "depression",
        "physical_inactivity",
        "diabetes",
        "low_social_contact",
        "excessive_alcohol",
        "traumatic_brain_injury",
        "air_pollution",
        "vision_loss",
        "high_ldl_cholesterol"
    ]
    
    # Count how many risk factors are present
    risk_count = 0
    for factor in LANCET_FACTORS:
        if factors.get(factor, False):
            risk_count += 1
            
    # Max possible risk factors is 14. 
    # Having 5 or more is considered extremely high risk in this simplified model.
    environmental_base = min(risk_count / 5.0, 1.0)
    
    # Blend the objective environmental factors (50%) with subjective symptom severity (50%)
    final_env_score = (environmental_base * 0.5) + (symptom_severity * 0.5)
    
    return round(min(final_env_score, 1.0), 4)

def save_environmental_scores(session_id: int, factors: dict, symptom_severity: float, env_score: float) -> bool:
    """Saves the environmental and symptom scores to the database."""
    from database.connection import get_connection, release_connection
    
    conn = get_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO environmental_scores (
                session_id, education_less_than_secondary, hearing_loss, hypertension,
                smoking, obesity, depression, physical_inactivity, diabetes,
                low_social_contact, excessive_alcohol, traumatic_brain_injury,
                air_pollution, vision_loss, high_ldl_cholesterol,
                symptom_severity, environmental_risk_score
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (session_id) DO UPDATE SET
                education_less_than_secondary = EXCLUDED.education_less_than_secondary,
                hearing_loss = EXCLUDED.hearing_loss,
                hypertension = EXCLUDED.hypertension,
                smoking = EXCLUDED.smoking,
                obesity = EXCLUDED.obesity,
                depression = EXCLUDED.depression,
                physical_inactivity = EXCLUDED.physical_inactivity,
                diabetes = EXCLUDED.diabetes,
                low_social_contact = EXCLUDED.low_social_contact,
                excessive_alcohol = EXCLUDED.excessive_alcohol,
                traumatic_brain_injury = EXCLUDED.traumatic_brain_injury,
                air_pollution = EXCLUDED.air_pollution,
                vision_loss = EXCLUDED.vision_loss,
                high_ldl_cholesterol = EXCLUDED.high_ldl_cholesterol,
                symptom_severity = EXCLUDED.symptom_severity,
                environmental_risk_score = EXCLUDED.environmental_risk_score
        """, (
            session_id,
            factors.get("education_less_than_secondary", False),
            factors.get("hearing_loss", False),
            factors.get("hypertension", False),
            factors.get("smoking", False),
            factors.get("obesity", False),
            factors.get("depression", False),
            factors.get("physical_inactivity", False),
            factors.get("diabetes", False),
            factors.get("low_social_contact", False),
            factors.get("excessive_alcohol", False),
            factors.get("traumatic_brain_injury", False),
            factors.get("air_pollution", False),
            factors.get("vision_loss", False),
            factors.get("high_ldl_cholesterol", False),
            symptom_severity,
            env_score
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[Environmental DB] Error saving scores: {e}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)
