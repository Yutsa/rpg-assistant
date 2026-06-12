(ns rpg-assistant-web.api)

(defn- api-base []
  (if (= "5174" (.-port js/location))
    "http://127.0.0.1:8000"
    ""))

(defn api-url [path]
  (str (api-base) path))

(defn- parse-json [text]
  (when (seq text)
    (js/JSON.parse text)))

(defn fetch-json
  "Appel JSON via `js/fetch` (approche recommandée dans les tutos Replicant).
  Retourne une promesse `{:ok true :data ...}` ou `{:ok false :status :error}`."
  [path & [{:keys [method body]}]]
  (-> (js/fetch
       (api-url path)
       (clj->js
        (cond-> {:headers {"Accept" "application/json"}}
          method (assoc :method (name method))
          body (assoc :body (js/JSON.stringify (clj->js body))
                      :headers {"Content-Type" "application/json"
                                "Accept" "application/json"})))))
      (.then
       (fn [response]
         (-> (.text response)
             (.then
              (fn [text]
                (let [parsed (when (seq text)
                               (js->clj (parse-json text) :keywordize-keys true))]
                  (if (.-ok response)
                    {:ok true :data parsed}
                    {:ok false
                     :status (.-status response)
                     :error (or (:error parsed)
                                (str "HTTP " (.-status response)))}))))))
      (.catch
       (fn [err]
         {:ok false :status 0 :error (.-message err)}))))
