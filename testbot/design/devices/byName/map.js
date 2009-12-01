function (doc) {
  if (doc.type == "device") {
    emit(doc.name, doc);
  }
}
