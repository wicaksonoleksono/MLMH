# app/routes/admin/llm_analysis_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user, login_required
from ...decorators import raw_response
from ...services.llm.analysisService import LLMAnalysisService

llm_analysis_bp = Blueprint('llm_analysis', __name__, url_prefix='/admin/llm/analysis')


@llm_analysis_bp.route('/run/<session_id>', methods=['POST'])
@login_required
@raw_response
def run_analysis(session_id):
    """Run LLM conversation analysis for a session"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    
    try:
        # Run the analysis
        result = LLMAnalysisService.run_conversation_analysis(session_id)
        
        if result:
            return jsonify({
                "status": "OLKORECT",
                "message": "Analysis completed successfully",
                "data": {
                    "analysis_id": result.id,
                    "session_id": result.session_id,
                    "analysis_model_used": result.analysis_model_used,
                    "conversation_turns_analyzed": result.conversation_turns_analyzed,
                    "total_aspects_detected": result.total_aspects_detected,
                    "average_severity_score": result.average_severity_score,
                    "analysis_confidence": result.analysis_confidence,
                    "aspect_scores": result.aspect_scores,
                    "created_at": result.created_at.isoformat()
                }
            })
        else:
            return jsonify({
                "status": "SNAFU",
                "error": "Analysis failed. Check server logs for details."
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Analysis error for session {session_id}: {str(e)}")
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@llm_analysis_bp.route('/results/<session_id>', methods=['GET'])
@login_required
@raw_response
def get_analysis_results(session_id):
    """Get analysis results for a session"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    
    try:
        result = LLMAnalysisService.get_analysis_result(session_id)
        
        if result:
            return jsonify({
                "status": "OLKORECT",
                "data": {
                    "analysis_id": result.id,
                    "session_id": result.session_id,
                    "analysis_model_used": result.analysis_model_used,
                    "conversation_turns_analyzed": result.conversation_turns_analyzed,
                    "total_aspects_detected": result.total_aspects_detected,
                    "average_severity_score": result.average_severity_score,
                    "analysis_confidence": result.analysis_confidence,
                    "aspect_scores": result.aspect_scores,
                    "raw_analysis_result": result.raw_analysis_result,
                    "created_at": result.created_at.isoformat()
                }
            })
        else:
            return jsonify({
                "status": "SNAFU",
                "error": f"No analysis results found for session {session_id}"
            }), 404
            
    except Exception as e:
        current_app.logger.error(f"Error getting analysis for session {session_id}: {str(e)}")
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@llm_analysis_bp.route('/test', methods=['POST'])
@login_required
@raw_response
def test_analysis():
    """Test analysis functionality with sample conversation"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    
    try:
        data = request.get_json()
        
        # Get sample conversation from request or use default
        sample_conversation = data.get('sample_conversation', [
            {"role": "assistant", "message": "Hai! Apa kabar? Gimana akhir-akhir ini?"},
            {"role": "user", "message": "Hai juga. Hmm, biasa aja sih. Agak capek akhir-akhir ini."},
            {"role": "assistant", "message": "Oh gitu, capek kenapa emangnya? Kerjaan atau gimana?"},
            {"role": "user", "message": "Entah ya, rasanya kayak ga ada yang menarik lagi. Dulu suka banget main game, sekarang udah ga tertarik. Kerja juga kayak robot aja."},
            {"role": "assistant", "message": "Wah, itu pasti ga enak ya rasanya. Udah berapa lama merasa kayak gitu?"},
            {"role": "user", "message": "Kayaknya udah beberapa bulan deh. Tidur juga susah, sering kepikiran macem-macem tapi ga jelas. Kadang merasa bersalah sama keluarga karena jadi pendiam."}
        ])
        
        # Run test analysis
        test_result = LLMAnalysisService.test_analysis_with_sample_data(sample_conversation)
        
        return jsonify({
            "status": "OLKORECT",
            "message": "Test analysis completed",
            "data": test_result
        })
        
    except Exception as e:
        current_app.logger.error(f"Test analysis error: {str(e)}")
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@llm_analysis_bp.route('/preview-prompt', methods=['POST'])
@login_required
@raw_response
def preview_analysis_prompt():
    """Preview the analysis prompt that would be generated"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    
    try:
        from ...services.llm.analysisPromptBuilder import LLMAnalysisPromptBuilder
        from ...services.admin.llmService import LLMService
        
        data = request.get_json()
        
        # Get sample conversation and aspects from request
        sample_conversation = data.get('sample_conversation', [
            {"role": "assistant", "message": "Hai! Apa kabar?"},
            {"role": "user", "message": "Halo, biasa aja sih."}
        ])
        
        # Get aspects from current settings or use defaults
        llm_settings = LLMAnalysisService.get_llm_settings()
        depression_aspects = []
        analysis_scale = None
        
        if llm_settings and llm_settings.depression_aspects:
            if isinstance(llm_settings.depression_aspects, dict) and 'aspects' in llm_settings.depression_aspects:
                depression_aspects = llm_settings.depression_aspects['aspects']
            elif isinstance(llm_settings.depression_aspects, list):
                depression_aspects = llm_settings.depression_aspects
            else:
                depression_aspects = LLMService.get_enhanced_default_aspects()
        else:
            depression_aspects = LLMService.get_enhanced_default_aspects()
        
        # Get analysis scale - use default if not configured
        if llm_settings and llm_settings.analysis_scale:
            if isinstance(llm_settings.analysis_scale, dict) and 'scale' in llm_settings.analysis_scale:
                analysis_scale = llm_settings.analysis_scale['scale']
            elif isinstance(llm_settings.analysis_scale, list):
                analysis_scale = llm_settings.analysis_scale
        
        if not analysis_scale:
            analysis_scale = LLMService.DEFAULT_ANALYSIS_SCALE
        
        # Allow custom aspects from request
        if 'depression_aspects' in data:
            depression_aspects = data['depression_aspects']
        
        # Build the prompt
        prompt = LLMAnalysisPromptBuilder.build_full_analysis_prompt(
            conversation_messages=sample_conversation,
            depression_aspects=depression_aspects,
            analysis_scale=analysis_scale
        )
        
        return jsonify({
            "status": "OLKORECT",
            "data": {
                "prompt": prompt,
                "prompt_length": len(prompt),
                "aspects_count": len(depression_aspects),
                "conversation_turns": len(sample_conversation),
                "depression_aspects_used": depression_aspects
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Preview prompt error: {str(e)}")
        return jsonify({"status": "SNAFU", "error": str(e)}), 500


@llm_analysis_bp.route('/batch-run', methods=['POST'])
@login_required
@raw_response
def batch_run_analysis():
    """Run analysis for multiple sessions"""
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({"status": "SNAFU", "error": "Admin access required"}), 403
    
    try:
        data = request.get_json()
        session_ids = data.get('session_ids', [])
        
        if not session_ids:
            return jsonify({"status": "SNAFU", "error": "No session IDs provided"}), 400
        
        results = []
        
        for session_id in session_ids:
            try:
                result = LLMAnalysisService.run_conversation_analysis(session_id)
                if result:
                    results.append({
                        "session_id": session_id,
                        "status": "success",
                        "analysis_id": result.id,
                        "total_aspects_detected": result.total_aspects_detected,
                        "average_severity_score": result.average_severity_score
                    })
                else:
                    results.append({
                        "session_id": session_id,
                        "status": "failed",
                        "error": "Analysis failed"
                    })
            except Exception as e:
                results.append({
                    "session_id": session_id,
                    "status": "error",
                    "error": str(e)
                })
        
        successful_count = sum(1 for r in results if r["status"] == "success")
        
        return jsonify({
            "status": "OLKORECT",
            "message": f"Batch analysis completed: {successful_count}/{len(session_ids)} successful",
            "data": {
                "results": results,
                "total_sessions": len(session_ids),
                "successful_count": successful_count,
                "failed_count": len(session_ids) - successful_count
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Batch analysis error: {str(e)}")
        return jsonify({"status": "SNAFU", "error": str(e)}), 500