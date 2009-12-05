function (doc) {
  if (doc.type == 'job' && doc.status == 'pending') {
     emit([doc.product, 
           doc.platform['os.sysname'],
           doc.pool,
           doc.platform['os.version'],
           doc.platform['hardware'],
           doc.platform['memory'],
           doc.platform['bpp'], 
           doc.platform['screenh'],
           doc.platform['screenw']],
           doc);
  }
}
