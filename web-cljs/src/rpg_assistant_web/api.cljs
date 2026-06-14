(ns rpg-assistant-web.api
  (:require [clojure.string :as str]))

(defn- api-base []
  (if (= "5174" (.-port js/location))
    "http://127.0.0.1:8000"
    ""))

(defn api-url [path]
  (str (api-base) path))

(defn page-render-url
  [document-id page-number & [{:keys [dpi pdf-path]}]]
  (let [params (js/URLSearchParams.)
        _ (when dpi (.set params "dpi" (str dpi)))
        _ (when (seq pdf-path) (.set params "pdf_path" pdf-path))
        query (.toString params)
        base (api-url (str "/documents/" document-id "/pages/" page-number "/render"))]
    (if (seq query)
      (str base "?" query)
      base)))

(defn- parse-json [text]
  (when (seq text)
    (js/JSON.parse text)))

(defn- response->result [response text]
  (let [parsed (when (seq text)
                 (js->clj (parse-json text) :keywordize-keys true))]
    (if (.-ok response)
      {:ok true :data parsed}
      {:ok false
       :status (.-status response)
       :body parsed
       :error (or (:error parsed)
                  (str "HTTP " (.-status response)))})))

(defn fetch-json
  [path & [{:keys [method body]}]]
  (let [request (js/fetch
                 (api-url path)
                 (clj->js
                  (cond-> {:headers {"Accept" "application/json"}}
                    method (assoc :method (name method))
                    body (assoc :body (js/JSON.stringify (clj->js body))
                                :headers {"Content-Type" "application/json"
                                          "Accept" "application/json"}))))]
    (.catch
     (.then request
            (fn [response]
              (.then (.text response)
                     (fn [text] (response->result response text)))))
     (fn [err]
       {:ok false :status 0 :error (.-message err)}))))
