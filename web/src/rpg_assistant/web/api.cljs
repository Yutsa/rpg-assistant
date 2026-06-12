(ns rpg-assistant.web.api)

(def api-base
  (when (exists? js/location)
    (let [port (.-port js/location)]
      (when (or (= port "5173") (= port "8765"))
        "/api"))))

(defn- parse-json [text]
  (when (seq text)
    (js/JSON.parse text)))

(defn- error-body-from-response [response text]
  (try
    (if (seq text)
      (parse-json text)
      #js {:error (str "HTTP " (.-status response))})
    (catch :default _
      #js {:error (or text (str "HTTP " (.-status response)))})))

(defn ApiClientError [status body]
  (let [err (js/Error. (or (.-error body) (str "HTTP " status)))]
    (set! (.-name err) "ApiClientError")
    (set! (.-status err) status)
    (set! (.-body err) body)
    err))

(defn api-client-error? [x]
  (instance? js/Error x))

(defn error-status [err]
  (when (api-client-error? err)
    (.-status err)))

(defn error-body [err]
  (when (api-client-error? err)
    (.-body err)))

(defn- parse-ok-response [response]
  (cond
    (= (.-status response) 204) (js/Promise.resolve nil)
    (.includes (or (.get (.-headers response) "content-type") "") "application/json")
    (.then (.text response)
           (fn [text]
             (if (seq text) (parse-json text) #js {})))
    :else (js/Promise.resolve response)))

(defn api-fetch
  ([path] (api-fetch path #js {}))
  ([path init]
   (let [url (if (.startsWith path "http") path (str api-base path))]
     (.then (js/fetch url init)
            (fn [response]
              (if (.-ok response)
                (parse-ok-response response)
                (.then (.text response)
                       (fn [text]
                         (throw (ApiClientError (.-status response)
                                                  (error-body-from-response response text)))))))))))

(defn page-render-url
  [document-id page-number & [{:keys [dpi pdf-path]}]]
  (let [params (js/URLSearchParams.)
        _ (when dpi (.set params "dpi" (str dpi)))
        _ (when pdf-path (.set params "pdf_path" pdf-path))
        query (.toString params)
        base (str api-base "/documents/" document-id "/pages/" page-number "/render")]
    (if (seq query)
      (str base "?" query)
      base)))
