(ns rpg.ingest.test-fixtures.pdf
  (:import [java.io File]
           [org.apache.pdfbox.pdmodel PDDocument PDPage]
           [org.apache.pdfbox.pdmodel.common PDRectangle]
           [org.apache.pdfbox.pdmodel.font PDType1Font]
           [org.apache.pdfbox.pdmodel.font Standard14Fonts$FontName]
           [org.apache.pdfbox.pdmodel PDPageContentStream]))

(defn- write-line [content-stream font-size text x-offset y-offset]
  (.beginText content-stream)
  (.setFont content-stream (PDType1Font. Standard14Fonts$FontName/HELVETICA) font-size)
  (.newLineAtOffset content-stream x-offset y-offset)
  (.showText content-stream text)
  (.endText content-stream))

(defn create-mixed-font-line-pdf [file-path]
  (let [file (File. file-path)]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)
            y (- page-height 100)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (.beginText content-stream)
          (.setFont content-stream (PDType1Font. Standard14Fonts$FontName/HELVETICA) 12)
          (.newLineAtOffset content-stream 72 y)
          (.showText content-stream "Normal ")
          (.setFont content-stream (PDType1Font. Standard14Fonts$FontName/HELVETICA_BOLD) 12)
          (.showText content-stream "bold")
          (.setFont content-stream (PDType1Font. Standard14Fonts$FontName/HELVETICA) 12)
          (.showText content-stream " text.")
          (.endText content-stream))
        (.save document file))
      (.getAbsolutePath file))))

(defn create-sample-pdf [file-path & {:keys [lines]
                                      :or {lines ["Premiere ligne de test." "Deuxieme ligne de test."]}}]
  (let [file (File. file-path)]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (doseq [[index line-text] (map-indexed vector lines)]
            (write-line content-stream 12 line-text 72 (- page-height 100 (* index 24)))))
        (.save document file))
      (.getAbsolutePath file))))

(defn create-drop-cap-paragraph-pdf [file-path]
  (let [file (File. file-path)]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)
            left 72
            wrap (+ left 28)
            line1-y (- page-height 160)
            line2-y (- page-height 184)
            line3-y (- page-height 208)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (write-line content-stream 27 "S" left line1-y)
          (write-line content-stream 10 "i beaucoup ont oublie les chroniques des" wrap line1-y)
          (write-line content-stream 10 "Terres d'Osgild, certains essaient de decou-" left line2-y)
          (write-line content-stream 10 "vrir les secrets de son passe." left line3-y))
        (.save document file))
      (.getAbsolutePath file))))
