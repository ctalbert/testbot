function (doc) {
  if (doc.type == 'job' && doc.product) {
    emit(doc.product, 1);
  }
}

