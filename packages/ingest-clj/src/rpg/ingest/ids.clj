(ns rpg.ingest.ids
  (:import [java.io FileInputStream]
           [java.math BigInteger]
           [java.security MessageDigest]
           [java.util UUID]))

(defn new-id
  "Generate a prefixed id aligned with rpg_core.storage.ids.new_id."
  [prefix]
  (str prefix "_" (subs (.replace (str (UUID/randomUUID)) "-" "") 0 12)))

(defn document-id-from-hash
  [content-hash]
  (str "doc_" (subs content-hash 0 12)))

(defn page-block-id
  [document-id page-number block-index]
  (format "block_%s_%03d_%03d" document-id page-number block-index))

(defn chunk-id
  [document-id page-start index]
  (format "chunk_%s_%03d_%03d" document-id page-start index))

(defn page-id
  [document-id page-number]
  (format "page_%s_%04d" document-id page-number))

(defn hash-file
  [path]
  (let [digest (MessageDigest/getInstance "SHA-256")
        buffer (byte-array 65536)]
    (with-open [in (FileInputStream. (java.io.File. path))]
      (loop []
        (let [n (.read in buffer)]
          (when (pos? n)
            (.update digest buffer 0 n)
            (recur)))))
    (format "%064x" (BigInteger. 1 (.digest digest)))))
