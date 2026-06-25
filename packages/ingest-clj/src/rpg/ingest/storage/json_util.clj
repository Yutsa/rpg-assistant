(ns rpg.ingest.storage.json-util
  (:require [cheshire.core :as json]
            [clojure.string :as str]))

(defn- snake-case-key [k]
  (-> (name k) (str/replace "-" "_")))

(defn encode-json
  "Encode a Clojure map to a JSON string with snake_case keys."
  [value]
  (json/generate-string value {:key-fn snake-case-key}))

(defn decode-json
  [s]
  (when s
    (json/parse-string s true)))
