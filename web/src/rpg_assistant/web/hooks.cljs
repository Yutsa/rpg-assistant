(ns rpg-assistant.web.hooks
  (:require [uix.core :as uix :refer [defhook]]))

(defn- storage-key [document-id]
  (str "rpg-assistant:pdf-path:" document-id))

(defhook use-pdf-path
  [document-id]
  (let [[pdf-path set-pdf-path!] (uix/use-state
                                  (fn []
                                    (when (some? js/window)
                                      (.getItem js/localStorage (storage-key document-id)))))
        [needs-override set-needs-override!] (uix/use-state false)
        [draft-path set-draft-path!] (uix/use-state (or pdf-path ""))]
    (uix/use-effect
      (fn []
        (let [stored (.getItem js/localStorage (storage-key document-id))]
          (set-pdf-path! stored)
          (set-draft-path! (or stored ""))
          (set-needs-override! false))
        js/undefined)
      [document-id])
    (let [set-pdf-path
          (uix/use-callback
           (fn [path]
             (let [trimmed (when path (.. path trim))]
               (if (seq trimmed)
                 (.setItem js/localStorage (storage-key document-id) trimmed)
                 (.removeItem js/localStorage (storage-key document-id)))
               (set-pdf-path! (when (seq trimmed) trimmed))
               (set-needs-override! false)))
           [document-id])
          save-draft (uix/use-callback
                      #(set-pdf-path draft-path)
                      [draft-path set-pdf-path])
          clear-path (uix/use-callback
                      (fn []
                        (set-pdf-path nil)
                        (set-draft-path! ""))
                      [set-pdf-path])]
      #js {:pdfPath pdf-path
           :needsOverride needs-override
           :setNeedsOverride set-needs-override!
           :draftPath draft-path
           :setDraftPath set-draft-path!
           :setPdfPath set-pdf-path
           :saveDraft save-draft
           :clearPath clear-path})))

(defhook use-async
  [fetch-fn deps]
  (let [[state set-state!] (uix/use-state #js {:loading true :data nil :error nil})]
    (uix/use-effect
      (fn []
        (set-state! #js {:loading true :data nil :error nil})
        (-> (fetch-fn)
            (.then (fn [data]
                     (set-state! #js {:loading false :data data :error nil})))
            (.catch (fn [err]
                      (set-state! #js {:loading false
                                       :data nil
                                       :error (if (instance? js/Error (.-message err))
                                                 (.-message err)
                                                 (str err))}))))
        js/undefined)
      (clj->js deps))
    state))
