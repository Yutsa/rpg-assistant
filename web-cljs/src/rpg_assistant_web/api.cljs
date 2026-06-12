(ns rpg-assistant-web.api
  (:require [cljs.core.async :refer [<! go]]
            [cljs.core.async.interop :refer-macros [<p!]]))

(defn- api-base []
  (if (= "5174" (.-port js/location))
    "http://127.0.0.1:8000"
    ""))

(defn api-url [path]
  (str (api-base) path))

(defn- parse-json [text]
  (when-not (empty? text)
    (js/JSON.parse text)))

(defn fetch-json
  "Returns a channel with `{:ok true :data ...}` or `{:ok false :status :error}`."
  [path & [{:keys [method body]}]]
  (go
    (try
      (let [response (<p! (js/fetch (api-url path)
                                    (clj->js (cond-> {:headers {"Accept" "application/json"}}
                                               method (assoc :method method)
                                               body (assoc :body (js/JSON.stringify (clj->js body))
                                                            :headers {"Content-Type" "application/json"
                                                                      "Accept" "application/json"})))))
            status (.-status response)]
        (if (< 199 status 300)
          (let [text (<p! (.text response))
                data (if (empty? text) nil (parse-json text))]
            {:ok true :data (js->clj data :keywordize-keys true)})
          (let [text (<p! (.text response))
                body (try (parse-json text) (catch :default _ text))]
            {:ok false
             :status status
             :error (if (map? body) (:error body) (str body))})))
      (catch :default err
        {:ok false :status 0 :error (.-message err)}))))
