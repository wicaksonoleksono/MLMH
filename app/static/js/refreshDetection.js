/**
 * Refresh Detection Logic
 * Handles page refresh detection and session reset for assessment pages
 */

function setupRefreshDetection(sessionId) {
    if (!sessionId) {
        console.warn('No session ID provided for refresh detection');
        return;
    }
    
    // Set flag when user leaves page (includes refresh)
    window.addEventListener('beforeunload', function() {
        // Store timestamp to detect recent refreshes
        sessionStorage.setItem('refreshingSession_' + sessionId, Date.now().toString());
        console.log('Refresh flag set for session ' + sessionId + ' at', Date.now());
    });
    
    // On page load, check if this is a legitimate refresh that should trigger reset
    window.addEventListener('DOMContentLoaded', function() {
        const refreshTimestamp = sessionStorage.getItem('refreshingSession_' + sessionId);
        if (refreshTimestamp) {
            const refreshTime = parseInt(refreshTimestamp);
            const currentTime = Date.now();
            const timeDiff = currentTime - refreshTime;
            
            // Remove the flag immediately
            sessionStorage.removeItem('refreshingSession_' + sessionId);
            
            // Only consider it a refresh if it happened within the last 5 seconds
            // This prevents old flags from triggering resets
            if (timeDiff < 5000) {
                // Only reset if we're not in the middle of a normal navigation flow
                // Check if we're coming from another assessment page (normal navigation)
                const referrer = document.referrer;
                const isFromAssessmentPage = referrer.includes('/assessment/phq') || referrer.includes('/assessment/llm');
                
                // Also check if this is likely a true refresh by checking if the page was loaded from cache
                const navigation = window.performance.getEntriesByType("navigation");
                const isLikelyRefresh = navigation.length > 0 && navigation[0].type === 'reload';
                
                if (!isFromAssessmentPage && isLikelyRefresh) {
                    console.log('Resetting session ' + sessionId + ' due to recent page refresh');
                    // Reset session and redirect to main menu
                    fetch(`/assessment/reset-session-on-refresh/${sessionId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    }).then(response => {
                        // Wait for the response to complete before redirecting
                        return response.text();
                    }).then(() => {
                        console.log('Session reset successful, redirecting to main menu');
                        // Redirect to main menu
                        window.location.href = `/`;
                    }).catch((error) => {
                        console.log('Session reset failed, redirecting to main menu anyway:', error);
                        // Even on error, redirect to main menu
                        window.location.href = `/`;
                    });
                } else {
                    console.log('Ignoring refresh flag - normal navigation or not a true refresh');
                }
            } else {
                console.log('Ignoring old refresh flag for session ' + sessionId + ', too old:', timeDiff, 'ms');
            }
        }
    });
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { setupRefreshDetection };
}