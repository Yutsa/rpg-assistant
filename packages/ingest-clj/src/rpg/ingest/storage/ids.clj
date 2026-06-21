(ns rpg.ingest.storage.ids
  (:import [java.nio.file Files Paths]
           [java.security MessageDigest]
           [java.util UUID]))

(defn new-run-id []
  (str "run_" (subs (.replace (.toString (UUID/randomUUID)) "-" "") 0 12)))

(defn content-hash [pdf-path]
  (let [digest (MessageDigest/getInstance "SHA-256")
        path (Paths/get pdf-path (into-array String []))
        bytes (. digest (digest (Files/readAllBytes path)))]
    (apply str (map #(format "%02x" (bit-and % 0xFF)) bytes))))

(defn document-id-from-hash [hash-value]
  (str "doc_" (subs hash-value 0 12)))

(defn page-id [document-id page-number]
  (format "page_%s_%04d" document-id page-number))

(defn page-block-id [document-id page-number block-index]
  (format "block_%s_%03d_%03d" document-id page-number block-index))
