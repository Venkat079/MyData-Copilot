// Simple API helper with JWT header handling
const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:5000/api";

function getToken() {
  return localStorage.getItem("jwtToken");
}

function headers(isJson = true) {
  const h = {};
  if (isJson) h["Content-Type"] = "application/json";
  const token = getToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export async function post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers(true),
    body: JSON.stringify(body),
  });
  return parseResponse(res);
}

export async function get(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: headers(true),
  });
  return parseResponse(res);
}

// src/api/api.js

// improved parseResponse
async function parseResponse(res) {
  const text = await res.text();
  let json = null;
  try {
    if (text) json = JSON.parse(text);
  } catch (e) {
    json = null;
  }

  if (!res.ok) {
    const err = new Error(
      (json && json.message) || text || `HTTP error ${res.status}`
    );
    err.status = res.status;
    err.body = json;
    throw err;
  }

  // if JSON parsed, return it, otherwise return raw text
  return json !== null ? json : text;
}

// improved upload function (XMLHttpRequest)
export async function upload(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      const status = xhr.status;
      const respText = xhr.responseText;
      let json = null;
      try {
        json = respText ? JSON.parse(respText) : null;
      } catch (err) {
        json = null;
      }

      if (status >= 200 && status < 300) {
        // success
        resolve(json !== null ? json : { ok: true, raw: respText });
      } else {
        const error = new Error(
          (json && json.message) || respText || `HTTP ${status}`
        );
        error.status = status;
        error.body = json;
        error.raw = respText;
        reject(error);
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during upload"));
    };

    xhr.send(formData);
  });
}

export async function del(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: headers(true),
  });
  return parseResponse(res);
}
