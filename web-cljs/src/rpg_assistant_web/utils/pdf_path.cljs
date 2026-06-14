(ns rpg-assistant-web.utils.pdf-path
  (:require [clojure.string :as str]))

(defn storage-key [document-id]
  (str "rpg-assistant:pdf-path:" document-id))

(defn load-path [document-id]
  (js/localStorage.getItem (storage-key document-id)))

(defn save-path! [document-id path]
  (let [trimmed (some-> path str/trim seq)]
    (if trimmed
      (js/localStorage.setItem (storage-key document-id) (str/trim path))
      (js/localStorage.removeItem (storage-key document-id)))))

(defn clear-path! [document-id]
  (js/localStorage.removeItem (storage-key document-id)))
