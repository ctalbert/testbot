function (doc) {
  if (doc.type == "device") {
    emit(doc.status, doc);
  }
}
