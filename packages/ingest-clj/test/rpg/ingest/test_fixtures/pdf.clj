(ns rpg.ingest.test-fixtures.pdf
  (:import [java.io File]
           [org.apache.pdfbox.pdmodel PDDocument PDPage]
           [org.apache.pdfbox.pdmodel.common PDRectangle]
           [org.apache.pdfbox.pdmodel.font PDType1Font]
           [org.apache.pdfbox.pdmodel.font Standard14Fonts$FontName]
           [org.apache.pdfbox.pdmodel PDPageContentStream]))

(defn- write-line [content-stream font-size text offset-y]
  (.beginText content-stream)
  (.setFont content-stream (PDType1Font. Standard14Fonts$FontName/HELVETICA) font-size)
  (.newLineAtOffset content-stream 72 offset-y)
  (.showText content-stream text)
  (.endText content-stream))

(defn create-sample-pdf [file-path & {:keys [lines]
                                      :or {lines ["Premiere ligne de test." "Deuxieme ligne de test."]}}]
  (let [file (File. file-path)]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (doseq [[index line-text] (map-indexed vector lines)]
            (write-line content-stream 12 line-text (- page-height 100 (* index 24)))))
        (.save document file))
      (.getAbsolutePath file))))
