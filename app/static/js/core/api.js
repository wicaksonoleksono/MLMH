// app/static/js/core/api.js
// Core API helper functions for authentication and HTTP requests

function setAuthToken(token) {
  localStorage.setItem("jwt_token", token);
}

function getAuthToken() {
  return localStorage.getItem("jwt_token");
}

function clearAuthToken() {
  localStorage.removeItem("jwt_token");
}

async function apiCall(url, method = "GET", data = null) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };

  const token = getAuthToken();
  if (token) {
    options.headers["Authorization"] = `Bearer ${token}`;
  }

  if (data) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(url, options);
    const responseText = await response.text();

    if (response.status === 401) {
      clearAuthToken();
    }

    // Try to parse as JSON
    try {
      return JSON.parse(responseText);
    } catch (parseError) {
      return {
        status: "SNAFU",
        error: "Invalid JSON response: " + responseText,
      };
    }
  } catch (error) {
    return { status: "SNAFU", error: error.message };
  }
}
