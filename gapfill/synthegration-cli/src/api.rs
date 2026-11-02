use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE, ACCEPT};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::error::Error;

const BASE_URL: &str = "https://chat.deepseek.com";
const POW_URL: &str = "/api/v0/chat/create_pow_challenge";

#[derive(Clone)]
pub struct DeepSeekClient {
    client: reqwest::blocking::Client,
    token: String,
    session_id: Option<String>,
    headers: HeaderMap,
}

impl DeepSeekClient {
    pub fn new(token: String) -> Result<Self, Box<dyn Error>> {
        let mut headers = HeaderMap::new();
        headers.insert(AUTHORIZATION, HeaderValue::from_str(&format!("Bearer {}", token))?);
        headers.insert("X-Client-Platform", HeaderValue::from_static("web"));
        headers.insert("X-Client-Version", HeaderValue::from_static("1.3.0-auto-resume"));
        headers.insert("X-App-Version", HeaderValue::from_static("20241129.1"));
        headers.insert("X-Client-Locale", HeaderValue::from_static("en_US"));
        headers.insert("Origin", HeaderValue::from_static(BASE_URL));
        headers.insert("Referer", HeaderValue::from_str(&format!("{}/", BASE_URL))?);
        Ok(Self {
            client: reqwest::blocking::Client::new(),
            token,
            session_id: None,
            headers,
        })
    }

    pub fn create_session(&mut self, model_type: &str) -> Result<String, Box<dyn Error>> {
        let resp = self.client
            .post(format!("{}/api/v0/chat_session/create", BASE_URL))
            .headers(self.headers.clone())
            .json(&json!({"character_id": null, "model_type": model_type}))
            .send()?;
        let data: Value = resp.json()?;
        let sid = data["data"]["biz_data"]["id"].as_str()
            .ok_or("No session id")?
            .to_string();
        self.session_id = Some(sid.clone());
        Ok(sid)
    }

    pub fn chat_completion(&self, prompt: &str, session_id: &str) -> Result<String, Box<dyn Error>> {
        let mut headers = self.headers.clone();
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
        headers.insert(ACCEPT, HeaderValue::from_static("text/event-stream"));
        // TODO: POW challenge + solve
        let payload = json!({
            "chat_session_id": session_id,
            "prompt": prompt,
            "ref_file_ids": [],
            "stream": true,
            "model_type": "default"
        });
        let resp = self.client
            .post(format!("{}/api/v0/chat/completion", BASE_URL))
            .headers(headers)
            .json(&payload)
            .send()?;
        let mut full_text = String::new();
        for line in resp.text()?.lines() {
            if let Some(data) = line.strip_prefix("data: ") {
                if data == "[DONE]" { break; }
                if let Ok(chunk) = serde_json::from_str::<Value>(data) {
                    if let Some(v) = chunk.get("v").and_then(|v| v.as_str()) {
                        if v != "FINISHED" { full_text.push_str(v); }
                    }
                }
            }
        }
        Ok(full_text)
    }
}